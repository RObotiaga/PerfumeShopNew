# bot_telegram/bot_config.py
import os
from decouple import config as env

BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")  # ЗАМЕНИТЕ НА ВАШ ТОКЕН

# Google Sheets related
GSHEET_CREDENTIALS_PATH = "credentials.json"
# GSHEET_URL = "https://docs.google.com/spreadsheets/d/1hkMtbCZ8g774h56L0cwvVCgO3eW5XL8yC7QwtNtMvWI/edit?gid=0#gid=0" # ОБНОВЛЕНО из ТЗ
# Используйте GOOGLE_SHEET_URL из основного config.py для единообразия

# USER_AGREEMENT_PATH = "bot_telegram/data/user_agreement.txt" # УДАЛЕНО
USER_AGREEMENT_URL = env("USER_AGREEMENT_URL", "https://docs.google.com/document/d/1jl4L7KDjZITWqV7JFknq959F6rTMGflA/edit") # ДОБАВЛЕНО: Замените на реальный URL или установите через .env

ITEMS_PER_PAGE = 10

DEFAULT_PORTION_STEPS = {
    "Обычный": [1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0],
    "Совместный": [2.5, 5.0, 7.5, 10.0, 15.0, 20.0],
}

# Условия бесплатной доставки из ТЗ (стр. 6, 9, 10)
FREE_DELIVERY_CONDITIONS = [
    {"min_fragrances": 2, "min_volume_ml": 10},
    {"min_fragrances": 3, "min_volume_ml": 5},
    {"min_fragrances": 5, "min_volume_ml": 3},
    {"min_fragrances": 7, "min_volume_ml": 2},
    {"min_fragrances": 10, "min_volume_ml": 1},
]

# Шаги для объемных товаров из ТЗ (стр. 3, 5, 8, 13)
DEFAULT_PORTION_STEPS = {
    "Обычный": [1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0],
    "Совместный": [2.5, 5.0, 7.5, 10.0, 15.0, 20.0],
}
# Для штучных товаров шаг всегда 1, это будет обрабатываться отдельно

PRODUCT_STATUS_EMOJI = {
    "в наличии": "🟢",
    "активен": "🟢",
    "active": "🟢",
    "available": "🟢",
    "ограничено": "🟡",
    "limited": "🟡",
    "нет в наличии": "🔴",
    "out of stock": "🔴",
    "забронирован": "🔒",
}
DEFAULT_PRODUCT_EMOJI = "✨"

# Константы для callback_data (помогут избежать опечаток)
CALLBACK_USER_AGREEMENT_ACCEPT = "user_agreement_accept"
# CALLBACK_USER_AGREEMENT_VIEW = "user_agreement_view" # УДАЛЕНО, так как теперь это URL
CALLBACK_NAV_MAIN_MENU = "nav_main_menu"
CALLBACK_NAV_CATALOG = "nav_catalog"
CALLBACK_NAV_CATEGORY_SELECTED = "nav_cat_sel:"
CALLBACK_NAV_PRODUCT_SELECTED = "nav_prod_sel:"
CALLBACK_NAV_CART = "nav_cart"
CALLBACK_NAV_MY_ORDERS = "nav_my_orders"
CALLBACK_NAV_HELP = "nav_help"
CALLBACK_NAV_INFO = "nav_info"
CALLBACK_PRODUCT_PAGE = "prod_page:"
CALLBACK_PRODUCT_ADD_TO_CART = "prod_add_cart:"
CALLBACK_PRODUCT_CHANGE_QTY_CART = "prod_chg_qty:"
CALLBACK_CART_ITEM_CHANGE_QTY = "cart_item_chg_qty:"
CALLBACK_CART_CHECKOUT = "cart_checkout"
CALLBACK_CART_CLEAR = "cart_clear"
CALLBACK_CART_CONTINUE_SHOPPING = "cart_continue_shop"

# Тексты для кнопок (можно вынести сюда для легкой смены)
BUTTON_TEXT_AGREE = "✅ Согласен(на) и принимаю условия"
BUTTON_TEXT_VIEW_AGREEMENT = "📄 Ознакомиться с Политикой" # Текст кнопки останется, но она станет URL-кнопкой

# Файл для хранения состояния пользователя (FSMContext)
# from aiogram.fsm.storage.memory import MemoryStorage
# FSM_STORAGE = MemoryStorage()
# from aiogram.fsm.storage.redis import RedisStorage
# FSM_STORAGE = RedisStorage.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))