import os
import re
import logging

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Date,
    Boolean,
    Text,
    text,
)
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.inspection import inspect as sqlalchemy_inspect

import gspread

Base = declarative_base()


# --- ORM Model Definitions ---
# Python attribute names are in English (snake_case or PascalCase for classes).
# The first argument to Column() is the exact header name in Google Sheets (in Russian as per the source).


class Product(Base):
    __tablename__ = "Товары"  # Sheet name in Google Sheets

    # Python attribute: english_snake_case = Column("Russian Header Name in GSheet", ...)
    product_id = Column("ID Товара", Integer, primary_key=True, autoincrement=False)
    product_name = Column("Название Товара", String)
    photo_url = Column("Ссылка на фото", String)
    category = Column("Категория", String)
    description = Column("Описание", Text)
    price_per_unit = Column("Цена за единицу", Float)
    unit_of_measure = Column("Единица измерения", String)
    product_type = Column("Тип товара", String)
    portion_type = Column(
        "Тип распива", String
    )  # 'portion_type' might be more descriptive if "Тип распива" has a specific meaning
    order_step = Column("Шаг заказа", Float)
    available_quantity = Column("Доступное количество", Float)
    status = Column("Статус", String)

    def __repr__(self):
        return f"<Product(product_id='{self.product_id}', product_name='{self.product_name}')>"


class Order(Base):
    __tablename__ = "Заказы"
    order_number = Column("Номер заказа", String, primary_key=True)
    user_id = Column("ID пользователя", String)
    order_date = Column("дата", Date)  # 'order_date' is the Python attribute
    # For "Список товаров(ID:Тип:Количество)", we use 'key' for a clean Python attribute name
    item_list_raw = Column(
        "Список товаров(ID:Тип:Количество)", String, key="item_list_raw"
    )
    total_amount = Column("Общая сумма", Float)
    status = Column("Статус", String)

    def __repr__(self):
        return f"<Order(order_number='{self.order_number}', user_id='{self.user_id}')>"


class DeliveryType(Base):
    __tablename__ = "Тип доставки"
    delivery_type_name = Column(
        "Тип доставки", String, primary_key=True, key="delivery_type_name"
    )  # Explicit key for clarity
    cost = Column("Стоимость", Float)
    is_active = Column(
        "Активность", String, key="is_active"
    )  # 'is_active' is more Pythonic

    def __repr__(self):
        return f"<DeliveryType(delivery_type_name='{self.delivery_type_name}', is_active='{self.is_active}')>"


class PaymentSetting(Base):  # Singular for class name representing one setting entry
    __tablename__ = (
        "Настройка платежей"  # Assuming this is the GSheet name based on logs
    )
    payment_format = Column("Формат оплаты", String, primary_key=True)
    recipient_name = Column("Наименование получателя", String)
    account_number = Column("Номер счета", String)
    bank_name = Column("Банк", String)
    bic = Column("БИК", String)  # Bank Identification Code
    inn = Column("ИНН", String)  # Taxpayer Identification Number
    terminal_key = Column("TerminalKey", String)  # Already English-like
    password = Column("Password", String)  # Already English-like

    def __repr__(self):
        return f"<PaymentSetting(payment_format='{self.payment_format}')>"


class Mailing(Base):
    __tablename__ = "Рассылки"
    mailing_id = Column("ID рассылки", Integer, primary_key=True, autoincrement=False)
    message_text = Column("Текст сообщения", Text)
    # For "Время отправки (дата/время)", using 'key'
    send_time_str = Column("Время отправки (дата/время)", String, key="send_time_str")
    is_sent = Column("Отправлено", String, key="is_sent")

    def __repr__(self):
        return f"<Mailing(mailing_id='{self.mailing_id}', is_sent='{self.is_sent}')>"


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

        # These are the exact titles of the sheets in your Google Spreadsheet
        self.expected_sheet_titles = [
            "Товары",
            "Заказы",
            "Тип доставки",
            "Настройка платежей",
            "Рассылки",
        ]

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

        self.db_engine = create_engine(  # Renamed from self.engine
            "gsheets://",
            service_account_file=self.credentials_path,
            catalog=self.sheet_catalog,
            # echo=True
        )

        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.db_engine
        )

        # Map sheet titles (from GSheet) to ORM model classes
        self.model_map = {
            "Товары": Product,
            "Заказы": Order,
            "Тип доставки": DeliveryType,
            "Настройка платежей": PaymentSetting,  # Corrected to singular as class name
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
            gspread_client = gspread.service_account(
                filename=self.credentials_path
            )  # Renamed
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
        data_dict = {}  # Renamed
        for column_attribute in sqlalchemy_inspect(
            type(row_object)
        ).mapper.column_attrs:
            # column_attribute.key is the Python attribute name (e.g., product_id)
            data_dict[column_attribute.key] = getattr(row_object, column_attribute.key)
        return data_dict

    # --- CRUD МЕТОДЫ ---

    def create_row(
        self, sheet_alias: str, data_payload: dict
    ) -> dict | None:  # Renamed data
        model_class = self._get_model_by_alias(sheet_alias)
        db_session = self.SessionLocal()  # Renamed
        try:
            valid_data_payload = {}  # Renamed
            model_attributes = {
                col_attr.key
                for col_attr in sqlalchemy_inspect(model_class).mapper.column_attrs
            }  # Renamed

            for key, value in data_payload.items():
                if key in model_attributes:
                    column_definition = getattr(model_class, key)
                    if hasattr(
                        column_definition, "type"
                    ):  # Check if it's a ColumnProperty
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
                    else:  # Should not happen for standard column attributes
                        valid_data_payload[key] = value
                else:
                    logging.warning(
                        f"Key '{key}' from input data_payload is not in model '{model_class.__name__}'. Skipping."
                    )

            new_record = model_class(**valid_data_payload)
            db_session.add(new_record)
            db_session.commit()
            # db_session.refresh(new_record) # Potentially problematic with Shillelagh
            created_data_dict = self._row_to_dict(new_record)  # Renamed
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
    ) -> list[dict]:  # Renamed parameters
        model_class = self._get_model_by_alias(sheet_alias)
        db_session = self.SessionLocal()
        try:
            query = db_session.query(model_class)
            if filter_criteria:
                valid_filter_criteria = {}  # Renamed
                for key, value in filter_criteria.items():
                    if not hasattr(model_class, key):
                        raise ValueError(
                            f"Attribute '{key}' not found in model '{model_class.__name__}' for filtering."
                        )
                    valid_filter_criteria[key] = value
                query = query.filter_by(**valid_filter_criteria)

            if order_by_attributes:
                order_expressions = []
                for attribute_name in order_by_attributes:  # Renamed
                    is_descending = False  # Renamed
                    if attribute_name.startswith("-"):
                        is_descending = True
                        attribute_name = attribute_name[1:]
                    if not hasattr(model_class, attribute_name):
                        raise ValueError(
                            f"Attribute '{attribute_name}' not found in model '{model_class.__name__}' for sorting."
                        )
                    column_orm_attribute = getattr(
                        model_class, attribute_name
                    )  # Renamed
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
    ) -> int:  # Renamed
        model_class = self._get_model_by_alias(sheet_alias)
        db_session = self.SessionLocal()
        updated_rows_count = 0  # Renamed
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
        deleted_rows_count = 0  # Renamed
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

    def get_all_data_from_all_sheets(self) -> dict:  # Renamed
        all_sheets_data_map = {}  # Renamed
        for sheet_alias_key in self.model_map.keys():  # Renamed
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

    def close_connection(self):  # Renamed
        if self.db_engine:
            self.db_engine.dispose()
            logging.info("Connection to Shillelagh/SQLAlchemy closed.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    )

    # IMPORTANT: Use a REAL URL for your Google Sheet.
    # Create a COPY of your sheet for safe testing of CRUD operations!
    GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1BqVMocZczXIVy1i6LG97VOy3HA65jBxd2jsEZjcTf8c/edit?gid=0#gid=0"  # Replace with your test sheet URL
    CREDENTIALS_JSON_PATH = "credentials.json"  # Path to your credentials file

    # Before running, ensure that your Google Sheet uses a PERIOD (.) as the decimal separator
    # for numeric columns (e.g., "Цена за единицу").
    # In Google Sheets: File -> Spreadsheet settings -> General -> Locale (e.g., "United States" or "United Kingdom")

    if GOOGLE_SHEET_URL == "ВАШ_URL_GOOGLE_ТАБЛИЦЫ_ДЛЯ_ТЕСТОВ":
        print(
            "Please specify a real URL for your Google Sheet (preferably a test copy) in the GOOGLE_SHEET_URL variable."
        )
    elif not os.path.exists(CREDENTIALS_JSON_PATH):
        print(f"Credentials file '{CREDENTIALS_JSON_PATH}' not found.")
    else:
        sheet_reader = None
        try:
            sheet_reader = GoogleSheetReader(
                sheet_url=GOOGLE_SHEET_URL, credentials_path=CREDENTIALS_JSON_PATH
            )

            # Проверка наличия листа "Настройка платежей"
            payment_settings_sheet_name = "Настройка платежей"
            if payment_settings_sheet_name not in sheet_reader.sheet_catalog:
                print(
                    f"\nWARNING: Sheet '{payment_settings_sheet_name}' not found in catalog. CRUD operations for it might fail or be skipped."
                )
                print(
                    f"Found sheets in catalog: {list(sheet_reader.sheet_catalog.keys())}"
                )
                print(
                    f"Expected sheet titles by configuration: {sheet_reader.expected_sheet_titles}"
                )

            # Пример использования CRUD операций
            test_product_id_value = 99902

            # 0. Предварительная очистка
            print("\n--- PRE-CLEANUP (optional) ---")
            sheet_reader.delete_rows(
                "Товары", filter_criteria={"product_id": test_product_id_value}
            )

            # 1. CREATE
            print("\n--- CREATE ---")
            new_product_payload = {
                "product_id": test_product_id_value,
                "product_name": "CRUD Test Product",
                "category": "CRUD Test Category",
                "price_per_unit": 123.45,
                "status": "Active CRUD",
            }
            created_product_dict = sheet_reader.create_row(
                "Товары", new_product_payload
            )
            if created_product_dict:
                print(f"Created product: {created_product_dict}")
            else:
                print("Failed to create product.")

            # 2. READ
            print("\n--- READ ---")
            read_filter_criteria = {"product_id": test_product_id_value}
            retrieved_product_list = sheet_reader.read_rows(
                "Товары", filter_criteria=read_filter_criteria
            )
            if retrieved_product_list:
                print(f"Found test product: {retrieved_product_list[0]}")
            else:
                print(
                    f"Test product with ID {test_product_id_value} not found after creation (or creation failed)."
                )

            # 3. UPDATE
            print("\n--- UPDATE ---")
            if retrieved_product_list:
                update_filter_criteria = {"product_id": test_product_id_value}
                update_payload = {
                    "status": "Updated by CRUD v3",
                    "price_per_unit": 150.99,
                }
                updated_count = sheet_reader.update_rows(
                    "Товары",
                    filter_criteria=update_filter_criteria,
                    new_data_payload=update_payload,
                )
                print(f"Updated products count: {updated_count}")
                if updated_count > 0:
                    updated_test_product_list = sheet_reader.read_rows(
                        "Товары", filter_criteria={"product_id": test_product_id_value}
                    )
                    if updated_test_product_list:
                        print(f"Updated test product: {updated_test_product_list[0]}")
            else:
                print("Skipping UPDATE as test product was not found.")

            # 4. DELETE
            print("\n--- DELETE ---")
            product_to_delete_list = sheet_reader.read_rows(
                "Товары", filter_criteria={"product_id": test_product_id_value}
            )
            if product_to_delete_list:
                print(f"Product found for deletion: {product_to_delete_list[0]}")
                deleted_count = sheet_reader.delete_rows(
                    "Товары", filter_criteria={"product_id": test_product_id_value}
                )
                print(f"Deleted products count: {deleted_count}")

                product_after_delete_list = sheet_reader.read_rows(
                    "Товары", filter_criteria={"product_id": test_product_id_value}
                )
                if not product_after_delete_list:
                    print(
                        f"Product with ID {test_product_id_value} successfully deleted."
                    )
                else:
                    print(
                        f"ERROR: Product with ID {test_product_id_value} still exists after deletion attempt."
                    )
            else:
                print(
                    f"Test product with ID {test_product_id_value} not found for deletion."
                )

        except FileNotFoundError as e:
            logging.error(f"File error: {e}")
        except ValueError as ve:
            logging.error(
                f"ValueError during initialization or CRUD execution: {ve}",
                exc_info=True,
            )
        except Exception as e:
            logging.error(
                f"An unexpected error occurred at the top level: {e}", exc_info=True
            )
        finally:
            if sheet_reader:
                sheet_reader.close_connection()
