# robotiaga-perfumeshopnew/app/database/sheet_service.py
import os
import re
import logging
import asyncio
import time
import json
import datetime
from typing import Dict, List, Any, Optional, Type

# SQLAlchemy imports for async
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import (
    select,
    update as sqlalchemy_update_stmt,
    delete as sqlalchemy_delete_stmt,
    Float,
)

# Standard SQLAlchemy imports for Shillelagh (sync)
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.orm import Session as SyncSqlAlchemySession
from sqlalchemy.inspection import inspect as sqlalchemy_inspect

import gspread

# aiosqlite больше не нужен для прямого импорта, SQLAlchemy будет использовать его под капотом

from .models import (
    GSheetBase,
    Product,
    Order,
    DeliveryType,
    PaymentSetting,
    Mailing,
    SqliteBase,
    PendingSheetOperation,
    User,
)
from config import (
    EXPECTED_SHEET_TITLES,
    CACHE_REFRESH_INTERVAL_SECONDS,
    SQLITE_DB_PATH,  # PENDING_OPERATIONS_TABLE_NAME (имя таблицы берется из __tablename__ модели)
    QUEUE_WORKER_INTERVAL_SECONDS,
    QUEUE_WORKER_MAX_ATTEMPTS,
)

logger = logging.getLogger(__name__)


class AsyncSheetServiceWithQueue:
    def __init__(
        self,
        sheet_url: str,
        credentials_path: str,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self.sheet_url = sheet_url
        self.gsheet_credentials_path = os.path.abspath(credentials_path)
        self.loop = loop or asyncio.get_event_loop()

        self._in_memory_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._in_memory_cache_last_updated: Dict[str, float] = {}
        self._cache_lock = asyncio.Lock()

        self._gsheet_refresh_interval = CACHE_REFRESH_INTERVAL_SECONDS
        self._queue_worker_interval = QUEUE_WORKER_INTERVAL_SECONDS

        self._gsheet_periodic_refresh_task: Optional[asyncio.Task] = None
        self._queue_processor_task: Optional[asyncio.Task] = None
        self._is_shutting_down = asyncio.Event()
        self._initial_gsheet_cache_populated = asyncio.Event()

        if not os.path.exists(self.gsheet_credentials_path):
            raise FileNotFoundError(
                f"GSheet credentials file not found at: {self.gsheet_credentials_path}"
            )

        self.spreadsheet_id = self._extract_spreadsheet_id_sync(sheet_url)
        if not self.spreadsheet_id:
            raise ValueError("Could not extract spreadsheet ID from URL.")

        self.expected_gsheet_titles = EXPECTED_SHEET_TITLES
        self.gsheet_catalog: Dict[str, str] = {}

        self.gsheet_model_map: Dict[str, Type[GSheetBase]] = {
            "Товары": Product,
            "Заказы": Order,
            "Тип доставки": DeliveryType,
            "Настройка платежей": PaymentSetting,
            "Рассылки": Mailing,
            "Пользователи": User,
        }

        self.gsheet_catalog = self._build_gsheet_catalog_sync()
        if not self.gsheet_catalog:
            logger.warning(
                "GSheet catalog is empty. Data fetching from GSheets might fail."
            )
        # Синхронный движок для Shillelagh (Google Sheets)
        self.gsheet_db_engine = create_sync_engine(
            "gsheets://",
            service_account_file=self.gsheet_credentials_path,
            catalog=self.gsheet_catalog,
        )
        self.GSheetSessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.gsheet_db_engine,
            class_=SyncSqlAlchemySession,
        )

        # --- Асинхронный движок и фабрика сессий для SQLite ---
        self.sqlite_db_url = f"sqlite+aiosqlite:///{SQLITE_DB_PATH}"
        self.sqlite_async_engine = create_async_engine(
            self.sqlite_db_url
        )  # echo=True для отладки SQL
        self.AsyncSqliteSessionLocal = sessionmaker(
            bind=self.sqlite_async_engine, class_=AsyncSession, expire_on_commit=False
        )

        logger.info(
            "AsyncSheetServiceWithQueue initialized with async SQLite. Call 'await service.start_services()' to begin."
        )

    async def _ensure_sqlite_tables_exist(self):
        """Создает все таблицы, определенные в SqliteBase, если их нет."""
        async with self.sqlite_async_engine.begin() as conn:
            # await conn.run_sync(SqliteBase.metadata.drop_all) # Для тестов: удалить таблицы перед созданием
            await conn.run_sync(SqliteBase.metadata.create_all)
        logger.info(
            f"Ensured SQLite tables (defined in SqliteBase) exist at {SQLITE_DB_PATH}."
        )

    # === Синхронные хелперы для GSheet (остаются как есть, вызываются через to_thread) ===
    # _extract_spreadsheet_id_sync, _build_gsheet_catalog_sync,
    # _get_gsheet_model_by_alias_sync, _gsheet_row_to_dict_sync,
    # _fetch_single_gsheet_data_blocking, _gsheet_create_row_blocking,
    # _gsheet_update_rows_blocking, _gsheet_delete_rows_blocking
    # ОНИ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ, так как Shillelagh - синхронный драйвер
    def _extract_spreadsheet_id_sync(self, url: str) -> Optional[str]:  # Same
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
        return match.group(1) if match else None

    def _build_gsheet_catalog_sync(self) -> Dict[str, str]:  # Same
        catalog = {}
        try:
            gspread_client = gspread.service_account(
                filename=self.gsheet_credentials_path
            )
            spreadsheet = gspread_client.open_by_key(self.spreadsheet_id)
            logger.info(f"(Sync) Building GSheet catalog for: {spreadsheet.title}")
            found_titles = []
            for worksheet in spreadsheet.worksheets():
                title = worksheet.title
                found_titles.append(title)
                if title in self.expected_gsheet_titles:
                    url = f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit?headers=1#gid={worksheet.id}"
                    catalog[title] = url
                    logger.info(f"(Sync)  Added GSheet '{title}' to catalog: {url}")
            for expected in self.expected_gsheet_titles:
                if expected not in catalog:
                    logger.warning(
                        f"(Sync) Expected GSheet '{expected}' not in catalog. Found: {found_titles}"
                    )
        except Exception as e:
            logger.error(f"(Sync) Error building GSheet catalog: {e}", exc_info=True)
        return catalog

    def _get_gsheet_model_by_alias_sync(
        self, sheet_alias: str
    ) -> Type[GSheetBase]:  # Same
        model_class = self.gsheet_model_map.get(sheet_alias)
        if not model_class:
            raise ValueError(f"GSheet ORM model for alias '{sheet_alias}' not found.")
        if sheet_alias not in self.gsheet_catalog:
            raise ValueError(f"GSheet alias '{sheet_alias}' not in catalog.")
        return model_class

    def _gsheet_row_to_dict_sync(
        self, row_object: GSheetBase, model_class: Type[GSheetBase]
    ) -> Dict[str, Any]:  # Same
        if row_object is None:
            return {}
        data_dict = {}
        for col_attr in sqlalchemy_inspect(model_class).mapper.column_attrs:
            data_dict[col_attr.key] = getattr(row_object, col_attr.key)
        return data_dict

    def _fetch_single_gsheet_data_blocking(
        self, sheet_alias: str
    ) -> List[Dict[str, Any]]:  # Same
        logger.debug(f"(Sync) Fetching data from GSheet: {sheet_alias}")
        model_class = self._get_gsheet_model_by_alias_sync(sheet_alias)
        gsheet_session: SyncSqlAlchemySession = self.GSheetSessionLocal()
        try:
            results = gsheet_session.query(model_class).all()
            return [self._gsheet_row_to_dict_sync(row, model_class) for row in results]
        except Exception as e:
            logger.error(
                f"(Sync) Error fetching GSheet data for '{sheet_alias}': {e}",
                exc_info=True,
            )
            return []
        finally:
            gsheet_session.close()

    def _gsheet_create_row_blocking(
        self, sheet_alias: str, data_payload: dict
    ) -> Optional[dict]:  # Same logic
        model_class = self._get_gsheet_model_by_alias_sync(sheet_alias)
        gsheet_session: SyncSqlAlchemySession = self.GSheetSessionLocal()
        try:
            valid_data = {}
            model_attrs = {
                col.key for col in sqlalchemy_inspect(model_class).mapper.column_attrs
            }
            for key, value in data_payload.items():
                if key in model_attrs:
                    valid_data[key] = value
            new_record = model_class(**valid_data)
            gsheet_session.add(new_record)
            gsheet_session.commit()
            return_data = {}
            for attr_name in model_attrs:
                if attr_name in valid_data:
                    return_data[attr_name] = valid_data[attr_name]
                elif hasattr(new_record, attr_name):
                    return_data[attr_name] = getattr(new_record, attr_name)
            return return_data
        except Exception as e:
            gsheet_session.rollback()
            logger.error(
                f"(Sync) GSheet create_row error '{sheet_alias}': {e}", exc_info=True
            )
            return None
        finally:
            gsheet_session.close()

    def _gsheet_update_rows_blocking(
        self, sheet_alias: str, filter_criteria: dict, new_data: dict
    ) -> int:  # Same logic
        model_class = self._get_gsheet_model_by_alias_sync(sheet_alias)
        gsheet_session: SyncSqlAlchemySession = self.GSheetSessionLocal()
        updated_count = 0
        try:
            query = gsheet_session.query(model_class).filter_by(**filter_criteria)
            records_to_update = query.all()
            for record in records_to_update:
                for key, value in new_data.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
                updated_count += 1
            if updated_count > 0:
                gsheet_session.commit()
            return updated_count
        except Exception as e:
            gsheet_session.rollback()
            logger.error(
                f"(Sync) GSheet update_rows error '{sheet_alias}': {e}", exc_info=True
            )
            return 0
        finally:
            gsheet_session.close()

    def _gsheet_delete_rows_blocking(
        self, sheet_alias: str, filter_criteria: dict
    ) -> int:  # Same logic
        model_class = self._get_gsheet_model_by_alias_sync(sheet_alias)
        gsheet_session: SyncSqlAlchemySession = self.GSheetSessionLocal()
        deleted_count = 0
        try:
            records_to_delete = (
                gsheet_session.query(model_class).filter_by(**filter_criteria).all()
            )
            for record in records_to_delete:
                gsheet_session.delete(record)
                deleted_count += 1
            if deleted_count > 0:
                gsheet_session.commit()
            return deleted_count
        except Exception as e:
            gsheet_session.rollback()
            logger.error(
                f"(Sync) GSheet delete_rows error '{sheet_alias}': {e}", exc_info=True
            )
            return 0
        finally:
            gsheet_session.close()

    # === Asynchronous In-Memory Cache Management (остается как есть) ===
    # _populate_in_memory_cache_for_sheet, _populate_all_in_memory_caches,
    # _periodic_gsheet_cache_refresh_task, force_gsheet_in_memory_cache_refresh
    # ОНИ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ
    async def _populate_in_memory_cache_for_sheet(self, sheet_alias: str):  # Same
        logger.info(f"Populating in-memory cache for GSheet: {sheet_alias}")
        if (
            sheet_alias not in self.gsheet_model_map
            or sheet_alias not in self.gsheet_catalog
        ):
            logger.warning(
                f"GSheet alias '{sheet_alias}' invalid or not in catalog. Skipping cache population."
            )
            return
        data = await asyncio.to_thread(
            self._fetch_single_gsheet_data_blocking, sheet_alias
        )
        async with self._cache_lock:
            self._in_memory_cache[sheet_alias] = data
            self._in_memory_cache_last_updated[sheet_alias] = time.monotonic()
        logger.info(
            f"In-memory cache populated for GSheet '{sheet_alias}', {len(data)} rows."
        )

    async def _populate_all_in_memory_caches(self):  # Same
        logger.info("Populating all in-memory caches from GSheets...")
        tasks = [
            self._populate_in_memory_cache_for_sheet(alias)
            for alias in self.gsheet_model_map.keys()
            if alias in self.gsheet_catalog
        ]
        await asyncio.gather(*tasks)
        self._initial_gsheet_cache_populated.set()
        logger.info("Initial GSheet in-memory cache population complete.")

    async def _periodic_gsheet_cache_refresh_task(self):  # Same
        await self._initial_gsheet_cache_populated.wait()
        logger.info("Starting periodic GSheet in-memory cache refresh task.")
        while not self._is_shutting_down.is_set():
            try:
                await asyncio.sleep(self._gsheet_refresh_interval)
                if self._is_shutting_down.is_set():
                    break
                logger.info("Periodic GSheet in-memory cache refresh triggered.")
                await self._populate_all_in_memory_caches()
            except asyncio.CancelledError:
                logger.info("Periodic GSheet cache refresh task cancelled.")
                break
            except Exception as e:
                logger.error(
                    f"Error in periodic GSheet cache refresh: {e}", exc_info=True
                )
                await asyncio.sleep(60)

    async def force_gsheet_in_memory_cache_refresh(
        self, sheet_alias: Optional[str] = None
    ):  # Same
        if sheet_alias:
            if (
                sheet_alias not in self.gsheet_model_map
                or sheet_alias not in self.gsheet_catalog
            ):
                logger.warning(
                    f"Cannot refresh GSheet cache for '{sheet_alias}': invalid or not in catalog."
                )
                return
            await self._populate_in_memory_cache_for_sheet(sheet_alias)
        else:
            await self._populate_all_in_memory_caches()

    # === Asynchronous Read Operations (from In-Memory Cache - остается как есть) ===
    # get_data_from_cache, read_rows_from_cache
    # ОНИ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ
    async def get_data_from_cache(
        self, sheet_alias: str
    ) -> List[Dict[str, Any]]:  # Same
        await self._initial_gsheet_cache_populated.wait()
        if (
            sheet_alias not in self.gsheet_model_map
            or sheet_alias not in self.gsheet_catalog
        ):
            logger.warning(f"'{sheet_alias}' not configured or found for cache read.")
            if (
                sheet_alias not in self._in_memory_cache
                and sheet_alias in self.gsheet_model_map
                and sheet_alias in self.gsheet_catalog
            ):
                logger.info(
                    f"Cache miss for {sheet_alias} after init, attempting one-time GSheet population."
                )
                await self._populate_in_memory_cache_for_sheet(sheet_alias)
        async with self._cache_lock:
            return list(self._in_memory_cache.get(sheet_alias, []))

    async def read_rows_from_cache(  # Same logic
        self,
        sheet_alias: str,
        filter_criteria: Optional[Dict[str, Any]] = None,
        order_by_attributes: Optional[List[str]] = None,
        row_limit: Optional[int] = None,
        row_offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        sheet_data = await self.get_data_from_cache(sheet_alias)
        if not sheet_data:
            return []
        if filter_criteria:
            sheet_data = [
                row
                for row in sheet_data
                if all(row.get(k) == v for k, v in filter_criteria.items())
            ]
        if order_by_attributes:
            for attr_name in reversed(order_by_attributes):
                is_desc = attr_name.startswith("-")
                attr_actual = attr_name[1:] if is_desc else attr_name
                if sheet_data and attr_actual not in sheet_data[0]:
                    logger.warning(
                        f"Sort key '{attr_actual}' not in cached '{sheet_alias}'"
                    )
                    continue
                try:
                    sheet_data.sort(key=lambda x: x.get(attr_actual), reverse=is_desc)
                except TypeError:
                    logger.warning(
                        f"TypeError sorting '{sheet_alias}' by '{attr_actual}'."
                    )
        if row_offset:
            sheet_data = sheet_data[row_offset:]
        if row_limit:
            sheet_data = sheet_data[:row_limit]
        return sheet_data

    # === Asynchronous Write Operations (to SQLite Queue using SQLAlchemy Async ORM) ===
    async def _add_operation_to_sqlite_queue_orm(  # ИЗМЕНЕНО: на SQLAlchemy Async ORM
        self,
        sheet_alias: str,
        operation_type: str,
        filter_criteria: Optional[dict] = None,
        data_payload: Optional[dict] = None,
    ) -> int:
        op_id = -1
        async with self.AsyncSqliteSessionLocal() as sqlite_session:  # Используем асинхронную сессию
            async with sqlite_session.begin():  # Начинаем транзакцию
                try:
                    pending_op = PendingSheetOperation(
                        sheet_alias=sheet_alias,
                        operation_type=operation_type.upper(),
                        # SQLAlchemy ORM может автоматически сериализовать/десериализовать JSON, если тип колонки JSON
                        # В нашей модели мы указали String для _json полей, поэтому json.dumps нужен.
                        filter_criteria_json=(
                            json.dumps(filter_criteria) if filter_criteria else None
                        ),
                        data_payload_json=(
                            json.dumps(data_payload) if data_payload else None
                        ),
                        status="pending",
                        created_at=datetime.datetime.utcnow(),
                    )
                    sqlite_session.add(pending_op)
                    await sqlite_session.flush()  # Чтобы получить ID до коммита, если PK - автоинкремент
                    if pending_op.id is None:
                        logger.error(
                            f"Failed to get operation ID after SQLite flush for {sheet_alias} {operation_type}."
                        )
                        await sqlite_session.rollback()  # Откатываем, если ID не получен
                        return -1
                    op_id = pending_op.id
                    # Коммит транзакции произойдет автоматически при выходе из `async with sqlite_session.begin()`
                    logger.info(
                        f"Queued operation to SQLite (SQLAlchemy ORM): ID={op_id}, Sheet='{sheet_alias}', Op='{operation_type}'"
                    )
                except Exception as e:
                    logger.error(
                        f"Error adding operation to SQLite queue (SQLAlchemy ORM): {e}",
                        exc_info=True,
                    )
                    await sqlite_session.rollback()  # Явный откат при ошибке внутри блока
                    return -1
        return op_id

    async def _optimistically_update_in_memory_cache(  # Остается как есть (async)
        self,
        sheet_alias: str,
        operation_type: str,
        filter_criteria: Optional[dict] = None,
        data_payload: Optional[dict] = None,
    ):
        # ... (логика без изменений, как в предыдущем ответе)
        async with self._cache_lock:
            if sheet_alias not in self._in_memory_cache:
                logger.warning(f"Optimistic: cache for '{sheet_alias}' not found.")
                return
            current_data = self._in_memory_cache.get(sheet_alias, [])
            op = operation_type.upper()
            if op == "CREATE" and data_payload:
                current_data.append(data_payload.copy())
                logger.debug(f"Optimistic CREATE cache '{sheet_alias}'")
            elif op == "UPDATE" and filter_criteria and data_payload:
                updated_c = 0
                for i, row in enumerate(current_data):
                    if all(row.get(k) == v for k, v in filter_criteria.items()):
                        current_data[i] = {**row, **data_payload}
                        updated_c += 1
                logger.debug(
                    f"Optimistic UPDATE cache '{sheet_alias}': {updated_c} affected."
                )
            elif op == "DELETE" and filter_criteria:
                new_d = []
                deleted_c = 0
                for row in current_data:
                    if not all(row.get(k) == v for k, v in filter_criteria.items()):
                        new_d.append(row)
                    else:
                        deleted_c += 1
                self._in_memory_cache[sheet_alias] = new_d
                logger.debug(
                    f"Optimistic DELETE cache '{sheet_alias}': {deleted_c} removed."
                )
            else:
                logger.warning(
                    f"Unknown op '{operation_type}' for optimistic cache update."
                )

    async def create_row(self, sheet_alias: str, data_payload: dict) -> Optional[dict]:
        op_id = await self._add_operation_to_sqlite_queue_orm(
            sheet_alias, "CREATE", data_payload=data_payload
        )
        if op_id == -1:
            return None
        await self._optimistically_update_in_memory_cache(
            sheet_alias, "CREATE", data_payload=data_payload
        )
        logger.info(
            f"CREATE op for '{sheet_alias}' queued (ID: {op_id}). Optimistic cache update done."
        )
        return data_payload

    async def update_rows(
        self, sheet_alias: str, filter_criteria: dict, new_data_payload: dict
    ) -> int:
        op_id = await self._add_operation_to_sqlite_queue_orm(
            sheet_alias,
            "UPDATE",
            filter_criteria=filter_criteria,
            data_payload=new_data_payload,
        )
        if op_id == -1:
            return 0
        await self._optimistically_update_in_memory_cache(
            sheet_alias,
            "UPDATE",
            filter_criteria=filter_criteria,
            data_payload=new_data_payload,
        )
        logger.info(
            f"UPDATE op for '{sheet_alias}' queued (ID: {op_id}). Optimistic cache update done."
        )
        return 1

    async def delete_rows(self, sheet_alias: str, filter_criteria: dict) -> int:
        op_id = await self._add_operation_to_sqlite_queue_orm(
            sheet_alias, "DELETE", filter_criteria=filter_criteria
        )
        if op_id == -1:
            return 0
        await self._optimistically_update_in_memory_cache(
            sheet_alias, "DELETE", filter_criteria=filter_criteria
        )
        logger.info(
            f"DELETE op for '{sheet_alias}' queued (ID: {op_id}). Optimistic cache update done."
        )
        return 1

    # === SQLite Queue Processor (Background Worker) using SQLAlchemy Async ORM ===
    async def _process_pending_operations_task(self):
        await self._initial_gsheet_cache_populated.wait()
        logger.info(
            "Starting SQLite pending operations processor task (SQLAlchemy Async ORM)."
        )
        while not self._is_shutting_down.is_set():
            op_id_processed: Optional[int] = None
            try:
                async with self.AsyncSqliteSessionLocal() as sqlite_session:
                    async with sqlite_session.begin():  # Начинаем транзакцию для выбора и обновления статуса
                        stmt = (
                            select(PendingSheetOperation)
                            .where(
                                PendingSheetOperation.status.in_(["pending", "retry"])
                            )
                            .order_by(PendingSheetOperation.created_at)
                            .limit(1)
                        )
                        result = await sqlite_session.execute(stmt)
                        operation_to_process = result.scalar_one_or_none()

                        if not operation_to_process:
                            # Явно закрываем сессию перед длительным сном, если нет операций
                            await sqlite_session.close()  # Закрываем сессию перед sleep
                            await asyncio.sleep(self._queue_worker_interval)
                            continue  # Переходим к следующей итерации цикла while

                        op_id_processed = operation_to_process.id
                        logger.info(
                            f"Processing operation ID {op_id_processed}: {operation_to_process.operation_type} on {operation_to_process.sheet_alias}"
                        )

                        operation_to_process.status = "processing"
                        operation_to_process.attempts += 1
                        operation_to_process.last_attempt_at = (
                            datetime.datetime.utcnow()
                        )
                        # Коммит для обновления статуса произойдет при выходе из `async with sqlite_session.begin()`

                    # Операция с GSheet происходит вне транзакции SQLite для статуса "processing"
                    op_type = operation_to_process.operation_type
                    sheet_alias = operation_to_process.sheet_alias
                    criteria = (
                        json.loads(operation_to_process.filter_criteria_json)
                        if operation_to_process.filter_criteria_json
                        else None
                    )
                    payload = (
                        json.loads(operation_to_process.data_payload_json)
                        if operation_to_process.data_payload_json
                        else None
                    )

                    success = False
                    result_info = None

                    if op_type == "CREATE" and payload:
                        result_info = await asyncio.to_thread(
                            self._gsheet_create_row_blocking, sheet_alias, payload
                        )
                        success = result_info is not None
                    elif op_type == "UPDATE" and criteria and payload:
                        result_info = await asyncio.to_thread(
                            self._gsheet_update_rows_blocking,
                            sheet_alias,
                            criteria,
                            payload,
                        )
                        success = result_info > 0  # Предполагая, что >0 означает успех
                    elif op_type == "DELETE" and criteria:
                        result_info = await asyncio.to_thread(
                            self._gsheet_delete_rows_blocking, sheet_alias, criteria
                        )
                        success = result_info > 0  # Предполагая, что >0 означает успех

                    # Обновляем/удаляем запись в SQLite в новой транзакции
                    async with self.AsyncSqliteSessionLocal() as sqlite_update_session:
                        async with sqlite_update_session.begin():
                            if success:
                                logger.info(
                                    f"GSheet Operation ID {op_id_processed} successful. Result: {result_info}. Removing from SQLite."
                                )
                                # Перезапросим объект в новой сессии для удаления
                                op_to_delete = await sqlite_update_session.get(
                                    PendingSheetOperation, op_id_processed
                                )
                                if op_to_delete:
                                    await sqlite_update_session.delete(op_to_delete)
                                # Коммит произойдет автоматически
                                # Обновляем кэш после успешной записи в GSheet
                                await self.force_gsheet_in_memory_cache_refresh(
                                    sheet_alias
                                )
                            else:
                                error_msg = f"GSheet operation ID {op_id_processed} failed (worker). See GSheet interaction logs."
                                logger.error(error_msg)
                                # Перезапросим объект для обновления
                                op_to_update = await sqlite_update_session.get(
                                    PendingSheetOperation, op_id_processed
                                )
                                if op_to_update:
                                    op_to_update.error_message = error_msg
                                    if (
                                        op_to_update.attempts
                                        >= QUEUE_WORKER_MAX_ATTEMPTS
                                    ):
                                        op_to_update.status = "failed_max_attempts"
                                    else:
                                        op_to_update.status = "retry"
                                # Коммит произойдет автоматически
            except Exception as e:
                logger.error(
                    f"Error in SQLite queue processor task (SQLAlchemy ORM): {e}",
                    exc_info=True,
                )
                if op_id_processed:  # Если ID операции был получен
                    try:
                        async with self.AsyncSqliteSessionLocal() as sqlite_err_session:
                            async with sqlite_err_session.begin():
                                op_to_mark_failed = await sqlite_err_session.get(
                                    PendingSheetOperation, op_id_processed
                                )
                                if op_to_mark_failed:
                                    op_to_mark_failed.status = "failed_worker_error"
                                    op_to_mark_failed.error_message = str(e)[
                                        :1000
                                    ]  # Ограничиваем длину сообщения об ошибке
                    except Exception as e_db_update:
                        logger.error(
                            f"Failed to mark operation {op_id_processed} as 'failed_worker_error' in SQLite: {e_db_update}"
                        )
                await asyncio.sleep(
                    self._queue_worker_interval
                )  # Пауза перед следующей попыткой цикла

            if self._is_shutting_down.is_set():
                break
        logger.info(
            "SQLite pending operations processor task (SQLAlchemy ORM) stopped."
        )

    # === Service Start/Stop ===
    async def start_services(self):
        await self._ensure_sqlite_tables_exist()  # Убедимся, что таблицы SQLite существуют

        if not self.gsheet_catalog:
            logger.warning(
                "GSheet catalog is empty. In-memory cache and GSheet interactions will be limited."
            )
            self._initial_gsheet_cache_populated.set()
        else:
            await self._populate_all_in_memory_caches()

        if (
            self._gsheet_periodic_refresh_task is None
            or self._gsheet_periodic_refresh_task.done()
        ):
            self._gsheet_periodic_refresh_task = asyncio.create_task(
                self._periodic_gsheet_cache_refresh_task()
            )
            logger.info("Background GSheet in-memory cache refresh task started.")

        if self._queue_processor_task is None or self._queue_processor_task.done():
            self._queue_processor_task = asyncio.create_task(
                self._process_pending_operations_task()
            )
            logger.info(
                "Background SQLite queue processor task (SQLAlchemy ORM) started."
            )

    async def close(self):
        logger.info(
            "Closing AsyncSheetServiceWithQueue (SQLAlchemy async SQLite version)..."
        )
        self._is_shutting_down.set()

        tasks_to_await = []
        if self._gsheet_periodic_refresh_task:
            tasks_to_await.append(self._gsheet_periodic_refresh_task)
        if self._queue_processor_task:
            tasks_to_await.append(self._queue_processor_task)

        for task in tasks_to_await:
            if task and not task.done():
                try:
                    task.cancel()
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout cancelling {task.get_name()}.")
                except asyncio.CancelledError:
                    logger.info(f"Task {task.get_name()} cancelled.")
                except Exception as e:
                    logger.error(f"Error shutting down {task.get_name()}: {e}")

        if self.gsheet_db_engine:
            await asyncio.to_thread(self.gsheet_db_engine.dispose)
        if self.sqlite_async_engine:
            await self.sqlite_async_engine.dispose()  # Закрываем асинхронный движок SQLite
        logger.info(
            "AsyncSheetServiceWithQueue (SQLAlchemy async SQLite version) closed."
        )
