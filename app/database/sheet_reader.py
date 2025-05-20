import os
import re
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.inspection import inspect as sqlalchemy_inspect
import gspread

from .models import Product, Order, DeliveryType, PaymentSetting, Mailing
from config import EXPECTED_SHEET_TITLES


class GoogleSheetReader:
    def __init__(self, sheet_url: str, credentials_path: str = "credentials.json"):
        self.sheet_url = sheet_url
        self.credentials_path = os.path.abspath(credentials_path)

        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(
                f"Credentials file not found at: {self.credentials_path}"
            )

        self.spreadsheet_id = self._extract_spreadsheet_id(sheet_url)
        if not self.spreadsheet_id:
            raise ValueError("Could not extract spreadsheet ID from URL.")

        self.expected_sheet_titles = EXPECTED_SHEET_TITLES
        self.sheet_catalog = self._build_sheet_catalog()

        if not self.sheet_catalog:
            expected_but_missing = [
                title
                for title in self.expected_sheet_titles
                if title not in self.sheet_catalog
            ]
            if expected_but_missing:
                logging.error(
                    f"The following expected sheets were not found in the Google Spreadsheet or their names do not match: {expected_but_missing}"
                )

        self.db_engine = create_engine(
            "gsheets://",
            service_account_file=self.credentials_path,
            catalog=self.sheet_catalog,
        )

        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.db_engine
        )

        self.model_map = {
            "Товары": Product,
            "Заказы": Order,
            "Тип доставки": DeliveryType,
            "Настройка платежей": PaymentSetting,
            "Рассылки": Mailing,
        }

    def _extract_spreadsheet_id(self, url: str) -> str | None:
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
        if match:
            return match.group(1)
        return None

    def _build_sheet_catalog(self) -> dict:
        catalog = {}
        try:
            gspread_client = gspread.service_account(filename=self.credentials_path)
            spreadsheet = gspread_client.open_by_key(self.spreadsheet_id)
            logging.info(f"Building catalog for spreadsheet: {spreadsheet.title}")
            found_titles_in_gsheet = []
            for worksheet in spreadsheet.worksheets():
                sheet_title = worksheet.title
                found_titles_in_gsheet.append(sheet_title)
                if sheet_title in self.expected_sheet_titles:
                    sheet_url_with_gid_and_headers = f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit?headers=1#gid={worksheet.id}"
                    catalog[sheet_title] = sheet_url_with_gid_and_headers
                    logging.info(
                        f"  Added sheet '{sheet_title}' to catalog: {sheet_url_with_gid_and_headers}"
                    )
                else:
                    logging.info(
                        f"  Sheet '{sheet_title}' (found in GSheet) skipped (not in self.expected_sheet_titles)."
                    )
            for expected_title in self.expected_sheet_titles:
                if expected_title not in found_titles_in_gsheet:
                    logging.warning(
                        f"Expected sheet '{expected_title}' NOT found in Google Spreadsheet. Found sheets: {found_titles_in_gsheet}"
                    )
        except gspread.exceptions.SpreadsheetNotFound:
            logging.error(
                f"Google Spreadsheet with ID '{self.spreadsheet_id}' not found."
            )
            raise
        except Exception as e:
            logging.error(f"Error building sheet catalog: {e}", exc_info=True)
            raise
        return catalog

    def _get_model_by_alias(self, sheet_alias: str):
        model_class = self.model_map.get(sheet_alias)
        if not model_class:
            logging.error(
                f"Alias '{sheet_alias}' not found in self.model_map. Available aliases: {list(self.model_map.keys())}"
            )
            raise ValueError(
                f"ORM model for sheet alias '{sheet_alias}' not found in configuration."
            )
        if sheet_alias not in self.sheet_catalog:
            raise ValueError(
                f"Sheet alias '{sheet_alias}' is not in the catalog (sheet not found in Google Sheets or name mismatch). Operation cannot be performed."
            )
        return model_class

    def _row_to_dict(self, row_object) -> dict:
        if row_object is None:
            return {}
        data_dict = {}
        for column_attribute in sqlalchemy_inspect(
            type(row_object)
        ).mapper.column_attrs:
            data_dict[column_attribute.key] = getattr(row_object, column_attribute.key)
        return data_dict

    def create_row(self, sheet_alias: str, data_payload: dict) -> dict | None:
        model_class = self._get_model_by_alias(sheet_alias)
        db_session = self.SessionLocal()
        try:
            valid_data_payload = {}
            model_attributes = {
                col_attr.key
                for col_attr in sqlalchemy_inspect(model_class).mapper.column_attrs
            }

            for key, value in data_payload.items():
                if key in model_attributes:
                    column_definition = getattr(model_class, key)
                    if hasattr(column_definition, "type"):
                        column_type = column_definition.type
                        if (
                            isinstance(column_type, Float)
                            and isinstance(value, str)
                            and "," in value
                        ):
                            try:
                                valid_data_payload[key] = float(value.replace(",", "."))
                            except ValueError:
                                logging.warning(
                                    f"Could not convert '{value}' to float for field {key}. Using as is."
                                )
                                valid_data_payload[key] = value
                        else:
                            valid_data_payload[key] = value
                    else:
                        valid_data_payload[key] = value
                else:
                    logging.warning(
                        f"Key '{key}' from input data_payload is not in model '{model_class.__name__}'. Skipping."
                    )

            new_record = model_class(**valid_data_payload)
            db_session.add(new_record)
            db_session.commit()
            created_data_dict = self._row_to_dict(new_record)
            logging.info(f"Created record in '{sheet_alias}': {created_data_dict}")
            return created_data_dict
        except Exception as e:
            db_session.rollback()
            logging.error(
                f"Error creating record in '{sheet_alias}': {e}", exc_info=True
            )
            return None
        finally:
            db_session.close()

    def read_rows(
        self,
        sheet_alias: str,
        filter_criteria: dict = None,
        order_by_attributes: list[str] = None,
        row_limit: int = None,
        row_offset: int = None,
    ) -> list[dict]:
        model_class = self._get_model_by_alias(sheet_alias)
        db_session = self.SessionLocal()
        try:
            query = db_session.query(model_class)
            if filter_criteria:
                valid_filter_criteria = {}
                for key, value in filter_criteria.items():
                    if not hasattr(model_class, key):
                        raise ValueError(
                            f"Attribute '{key}' not found in model '{model_class.__name__}' for filtering."
                        )
                    valid_filter_criteria[key] = value
                query = query.filter_by(**valid_filter_criteria)

            if order_by_attributes:
                order_expressions = []
                for attribute_name in order_by_attributes:
                    is_descending = False
                    if attribute_name.startswith("-"):
                        is_descending = True
                        attribute_name = attribute_name[1:]
                    if not hasattr(model_class, attribute_name):
                        raise ValueError(
                            f"Attribute '{attribute_name}' not found in model '{model_class.__name__}' for sorting."
                        )
                    column_orm_attribute = getattr(model_class, attribute_name)
                    order_expressions.append(
                        column_orm_attribute.desc()
                        if is_descending
                        else column_orm_attribute.asc()
                    )
                query = query.order_by(*order_expressions)

            if row_limit is not None:
                query = query.limit(row_limit)
            if row_offset is not None:
                query = query.offset(row_offset)

            results = query.all()
            return [self._row_to_dict(row) for row in results]
        except ValueError as ve:
            logging.error(
                f"ValueError while reading records from '{sheet_alias}': {ve}"
            )
            return []
        except Exception as e:
            logging.error(
                f"Error reading records from '{sheet_alias}': {e}", exc_info=True
            )
            return []
        finally:
            db_session.close()

    def update_rows(
        self, sheet_alias: str, filter_criteria: dict, new_data_payload: dict
    ) -> int:
        model_class = self._get_model_by_alias(sheet_alias)
        db_session = self.SessionLocal()
        updated_rows_count = 0
        try:
            valid_filter_criteria = {}
            for key, value in filter_criteria.items():
                if not hasattr(model_class, key):
                    raise ValueError(
                        f"Attribute '{key}' not found in model '{model_class.__name__}' for update criteria."
                    )
                valid_filter_criteria[key] = value

            valid_new_data_payload = {}
            model_attributes = {
                col_attr.key
                for col_attr in sqlalchemy_inspect(model_class).mapper.column_attrs
            }
            for key, value in new_data_payload.items():
                if key in model_attributes:
                    column_definition = getattr(model_class, key)
                    if hasattr(column_definition, "type"):
                        column_type = column_definition.type
                        if (
                            isinstance(column_type, Float)
                            and isinstance(value, str)
                            and "," in value
                        ):
                            try:
                                valid_new_data_payload[key] = float(
                                    value.replace(",", ".")
                                )
                            except ValueError:
                                logging.warning(
                                    f"Could not convert '{value}' to float for field {key} during update. Using as is."
                                )
                                valid_new_data_payload[key] = value
                        else:
                            valid_new_data_payload[key] = value
                    else:
                        valid_new_data_payload[key] = value
                else:
                    logging.warning(
                        f"Key '{key}' from new_data_payload is not in model '{model_class.__name__}'. Skipping for update."
                    )

            if not valid_new_data_payload:
                logging.warning(
                    f"No valid data provided for update in '{sheet_alias}'."
                )
                return 0

            query = db_session.query(model_class).filter_by(**valid_filter_criteria)
            records_to_update = query.all()

            if not records_to_update:
                logging.info(
                    f"No records found to update in '{sheet_alias}' with criteria: {valid_filter_criteria}"
                )
                return 0

            for record in records_to_update:
                for key, value in valid_new_data_payload.items():
                    setattr(record, key, value)
                updated_rows_count += 1

            db_session.commit()
            logging.info(f"Updated {updated_rows_count} records in '{sheet_alias}'.")
            return updated_rows_count
        except Exception as e:
            db_session.rollback()
            logging.error(
                f"Error updating records in '{sheet_alias}': {e}", exc_info=True
            )
            return 0
        finally:
            db_session.close()

    def delete_rows(self, sheet_alias: str, filter_criteria: dict) -> int:
        model_class = self._get_model_by_alias(sheet_alias)
        db_session = self.SessionLocal()
        deleted_rows_count = 0
        try:
            valid_filter_criteria = {}
            for key, value in filter_criteria.items():
                if not hasattr(model_class, key):
                    raise ValueError(
                        f"Attribute '{key}' not found in model '{model_class.__name__}' for deletion criteria."
                    )
                valid_filter_criteria[key] = value

            records_to_delete = (
                db_session.query(model_class).filter_by(**valid_filter_criteria).all()
            )

            if not records_to_delete:
                logging.info(
                    f"No records found to delete in '{sheet_alias}' with criteria: {valid_filter_criteria}"
                )
                return 0

            for record in records_to_delete:
                db_session.delete(record)
                deleted_rows_count += 1

            db_session.commit()
            logging.info(f"Deleted {deleted_rows_count} records from '{sheet_alias}'.")
            return deleted_rows_count
        except Exception as e:
            db_session.rollback()
            logging.error(
                f"Error deleting records from '{sheet_alias}': {e}", exc_info=True
            )
            return 0
        finally:
            db_session.close()

    def get_all_data_from_all_sheets(self) -> dict:
        all_sheets_data_map = {}
        for sheet_alias_key in self.model_map.keys():
            if sheet_alias_key not in self.sheet_catalog:
                logging.warning(
                    f"Sheet alias '{sheet_alias_key}' is not in catalog, skipping in get_all_data_from_all_sheets."
                )
                all_sheets_data_map[sheet_alias_key] = {
                    "error": f"Sheet alias '{sheet_alias_key}' not found in the configured catalog."
                }
                continue
            all_sheets_data_map[sheet_alias_key] = self.read_rows(sheet_alias_key)
        return all_sheets_data_map

    def close_connection(self):
        if self.db_engine:
            self.db_engine.dispose()
            logging.info("Connection to Shillelagh/SQLAlchemy closed.")
