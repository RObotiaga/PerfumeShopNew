import os
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
)

# Путь к файлу с учетными данными Google
CREDENTIALS_JSON_PATH = "credentials.json"

# URL Google таблицы
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1BqVMocZczXIVy1i6LG97VOy3HA65jBxd2jsEZjcTf8c/edit?gid=0#gid=0"

# Ожидаемые названия листов в Google таблице
EXPECTED_SHEET_TITLES = [
    "Товары",
    "Заказы",
    "Тип доставки",
    "Настройка платежей",
    "Рассылки",
]

# Проверка наличия файла с учетными данными
if not os.path.exists(CREDENTIALS_JSON_PATH):
    logging.error(f"Credentials file '{CREDENTIALS_JSON_PATH}' not found.")
