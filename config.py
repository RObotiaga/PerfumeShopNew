# robotiaga-perfumeshopnew/config.py
import os
import logging

# Logging setup
# (оставляем как есть)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
)

# Path to Google credentials file
CREDENTIALS_JSON_PATH = "credentials.json"

# Google Sheet URL
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1BqVMocZczXIVy1i6LG97VOy3HA65jBxd2jsEZjcTf8c/edit?gid=0#gid=0"

# Expected sheet titles in Google Sheet
EXPECTED_SHEET_TITLES = [
    "Товары",
    "Заказы",
    "Тип доставки",
    "Настройка платежей",
    "Рассылки",
]

# Cache settings
CACHE_REFRESH_INTERVAL_SECONDS = 5 * 60  # 5 minutes

# SQLite database path (for pending operations queue)
SQLITE_DB_PATH = "sheet_operations_queue.sqlite3" # Будет создан в корне проекта
PENDING_OPERATIONS_TABLE_NAME = "pending_sheet_operations"

# Worker settings
QUEUE_WORKER_INTERVAL_SECONDS = 30 # Как часто воркер проверяет очередь SQLite
QUEUE_WORKER_MAX_ATTEMPTS = 5 # Макс. попыток для одной операции

# Check for credentials file existence
if not os.path.exists(CREDENTIALS_JSON_PATH):
    logging.error(
        f"Credentials file '{CREDENTIALS_JSON_PATH}' not found. "
        f"Place it in the project root or update the path in config.py."
    )

# Define LOGGING_CONFIG if you want to use dictConfig, otherwise basicConfig works
LOGGING_CONFIG = None # Пример: {'version': 1, ...}