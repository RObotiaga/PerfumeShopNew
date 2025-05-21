# robotiaga-perfumeshopnew/DEBUG.py
import asyncio
import logging
import datetime
import random
import uuid  # Для генерации уникальных номеров заказов

from app.database import AsyncSheetServiceWithQueue
from config import (
    GOOGLE_SHEET_URL,
    CREDENTIALS_JSON_PATH,
    QUEUE_WORKER_INTERVAL_SECONDS,
    LOGGING_CONFIG, # Используем LOGGING_CONFIG, если он определен
)

# Настройка логирования (аналогично main.py)
if LOGGING_CONFIG:
    import logging.config
    logging.config.dictConfig(LOGGING_CONFIG)
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    )
logger = logging.getLogger(__name__)

# --- Тестовые данные для Товаров ---
# Убедитесь, что product_id уникальны
TEST_PRODUCTS_DATA = [
    {
        "product_id": 1001,
        "product_name": "Chanel N°5 (Тест)",
        "photo_url": "https://www.chanel.com/images/q_auto,f_auto,fl_lossy,dpr_auto/w_1920/FSH-107160-1920x1920.jpg",
        "category": "Женская парфюмерия",
        "description": "Легендарный цветочный альдегидный аромат.",
        "price_per_unit": 150.0,
        "unit_of_measure": "мл",
        "product_type": "Объемный",
        "portion_type": "Обычный",
        "order_step": "1;2;3;5;10", # Для "мл"
        "available_quantity": 50.0,
        "status": "В наличии",
    },
    {
        "product_id": 1002,
        "product_name": "Dior Sauvage (Тест)",
        "photo_url": "https://www.dior.com/beauty/version-5.1432748111/resize-image/ep/0/0/0/0/0/0/0/0/0/w1050_q85_webp/zjpeg/focus-crop/w1050_h800_nofocus/products/Y0996001.jpg",
        "category": "Мужская парфюмерия",
        "description": "Свежий и пряный аромат с нотами бергамота и амброксана.",
        "price_per_unit": 120.0,
        "unit_of_measure": "мл",
        "product_type": "Объемный",
        "portion_type": "Обычный",
        "order_step": "2.5;5;7.5;10", # Для "мл"
        "available_quantity": 30.0,
        "status": "В наличии",
    },
    {
        "product_id": 1003,
        "product_name": "Tom Ford Oud Wood (Тест)",
        "photo_url": "https://www.sephora.com/productimages/sku/s1447354-main-zoom.jpg",
        "category": "Унисекс",
        "description": "Роскошный древесный аромат с нотами уда, сандала и ванили.",
        "price_per_unit": 250.0,
        "unit_of_measure": "мл",
        "product_type": "Объемный",
        "portion_type": "Совместный",
        "order_step": "1;2.5;5",
        "available_quantity": 15.5,
        "status": "Ограничено",
    },
    {
        "product_id": 2001,
        "product_name": "Подарочный набор 'Весна' (Тест)",
        "photo_url": "https://example.com/gift_set_spring.jpg", # Замените на реальный URL, если есть
        "category": "Наборы",
        "description": "Набор из трех миниатюр популярных ароматов.",
        "price_per_unit": 3500.0,
        "unit_of_measure": "шт", # Штучный товар
        "product_type": "Штучный",
        "portion_type": None, # Не применимо для штучных
        "order_step": "1", # Для "шт"
        "available_quantity": 10.0, # 10 штук
        "status": "В наличии",
    },
    {
        "product_id": 1004,
        "product_name": "Creed Aventus (Тест - Забронирован)",
        "photo_url": "https://www.creedboutique.com/cdn/shop/products/aventus-cologne-cologne-creed-fragrances-306817_1024x.jpg",
        "category": "Мужская парфюмерия",
        "description": "Фруктовый шипровый аромат для мужчин.",
        "price_per_unit": 300.0,
        "unit_of_measure": "мл",
        "product_type": "Объемный",
        "portion_type": "Обычный",
        "order_step": "1;2;5",
        "available_quantity": 0.0, # Полностью забронирован/распродан
        "status": "Забронирован",
    }
]

# --- Тестовые данные для Заказов ---
# order_number должен быть уникальным
# user_id - это ID пользователя Telegram (число)
# item_list_raw формат: "IDТовара1:Тип:Количество,IDТовара2:Тип:Количество"
# Тип для item_list_raw: 'volume' или 'piece'. Можно упростить, если тип всегда ясен из товара.
# Для примера я буду использовать 'объемный'/'штучный' как в product_type
# и sheet_service не использует этот "Тип" при обработке заказа, он для информации.

TEST_ORDERS_DATA = [
    {
        "order_number": f"TEST-{uuid.uuid4().hex[:8].upper()}",
        "user_id": "123456789", # Пример ID пользователя
        "order_date": (datetime.date.today() - datetime.timedelta(days=random.randint(1, 30))).isoformat(),
        "item_list_raw": "1001:Объемный:5,2001:Штучный:1", # Chanel N°5 - 5мл, Набор 'Весна' - 1шт
        "total_amount": (150.0 * 5) + (3500.0 * 1), # (цена*кол-во) + (цена*кол-во)
        "delivery_cost": 250.0,
        "delivery_type_name": "СДЭК по Новосибирску",
        "delivery_address": "Новосибирск, ул. Ленина, д. 10, кв. 5",
        "comment": "Позвонить за час до доставки.",
        "status": "Принят",
    },
    {
        "order_number": f"TEST-{uuid.uuid4().hex[:8].upper()}",
        "user_id": "987654321",
        "order_date": (datetime.date.today() - datetime.timedelta(days=random.randint(1, 10))).isoformat(),
        "item_list_raw": "1002:Объемный:10", # Dior Sauvage - 10мл
        "total_amount": 120.0 * 10,
        "delivery_cost": 0.0, # Бесплатная доставка, например
        "delivery_type_name": "Самовывоз",
        "delivery_address": None, # Для самовывоза адрес не нужен
        "comment": "Заберу завтра после 18:00",
        "status": "В обработке",
    },
    {
        "order_number": f"TEST-{uuid.uuid4().hex[:8].upper()}",
        "user_id": "123456789", # Тот же пользователь, другой заказ
        "order_date": datetime.date.today().isoformat(),
        "item_list_raw": "1003:Объемный:2.5", # Tom Ford Oud Wood - 2.5мл
        "total_amount": 250.0 * 2.5,
        "delivery_cost": 350.0,
        "delivery_type_name": "Курьерская служба",
        "delivery_address": "Новосибирск, ул. Мира, д. 1, офис 101",
        "comment": "",
        "status": "Ожидает оплаты",
    }
]


async def populate_data(sheet_service: AsyncSheetServiceWithQueue):
    logger.info("--- STARTING DATA POPULATION ---")

    # --- Заполнение Товаров ---
    logger.info("\n--- POPULATING PRODUCTS ---")
    products_created_count = 0
    for product_payload in TEST_PRODUCTS_DATA:
        logger.info(f"Attempting to create product: {product_payload.get('product_name')}")
        # В реальном сценарии, если ID уже существует, create_row просто добавит новую строку.
        # Для тестовых данных это может быть приемлемо, или нужна логика "update_or_create".
        # Пока что просто создаем.
        created_product = await sheet_service.create_row("Товары", product_payload)
        if created_product:
            products_created_count += 1
            logger.info(f"Product '{product_payload.get('product_name')}' queued for creation. Optimistic data: {created_product}")
        else:
            logger.error(f"Failed to queue product '{product_payload.get('product_name')}' for creation.")
    logger.info(f"--- {products_created_count}/{len(TEST_PRODUCTS_DATA)} products queued for creation ---")

    # --- Заполнение Заказов ---
    logger.info("\n--- POPULATING ORDERS ---")
    orders_created_count = 0
    for order_payload in TEST_ORDERS_DATA:
        logger.info(f"Attempting to create order: {order_payload.get('order_number')}")
        created_order = await sheet_service.create_row("Заказы", order_payload)
        if created_order:
            orders_created_count += 1
            logger.info(f"Order '{order_payload.get('order_number')}' queued for creation. Optimistic data: {created_order}")
        else:
            logger.error(f"Failed to queue order '{order_payload.get('order_number')}' for creation.")
    logger.info(f"--- {orders_created_count}/{len(TEST_ORDERS_DATA)} orders queued for creation ---")

    # Даем время воркеру обработать очередь
    # Это время зависит от количества операций и интервала воркера
    # (N_operations / ops_per_worker_run) * worker_interval + buffer
    # Для ~10 операций, если воркер обрабатывает по одной: 10 * 30s = 300s.
    # Если он обрабатывает пачкой, то быстрее.
    # Для простоты, поставим значительное время, но не слишком долгое для отладки.
    # Учитываем, что каждая операция к GSheet тоже занимает время.
    total_ops = len(TEST_PRODUCTS_DATA) + len(TEST_ORDERS_DATA)
    # Примерная оценка: 5 секунд на операцию в GSheet + интервал воркера
    wait_time = (total_ops * 5) + QUEUE_WORKER_INTERVAL_SECONDS + 15
    logger.info(f"\n--- WAITING APPROX {wait_time} SECONDS FOR QUEUE WORKER TO PROCESS OPERATIONS ---")
    await asyncio.sleep(wait_time)

    logger.info("\n--- DATA POPULATION SCRIPT FINISHED ---")
    logger.info("--- Please check your Google Sheet to verify the data. ---")


async def main_debug_entry():
    logger.info("Starting DEBUG Data Population Script...")
    sheet_service_instance = None
    try:
        sheet_service_instance = AsyncSheetServiceWithQueue(
            sheet_url=GOOGLE_SHEET_URL, credentials_path=CREDENTIALS_JSON_PATH
        )
        await sheet_service_instance.start_services()
        logger.info("Sheet service initialized and background tasks started for DEBUG.")

        # Убедимся, что кэш GSheet загружен перед тем, как что-то делать (хотя для create это не так критично)
        await sheet_service_instance._initial_gsheet_cache_populated.wait()
        logger.info("Initial GSheet cache populated.")

        await populate_data(sheet_service_instance)

    except FileNotFoundError as e:
        logger.error(f"Configuration error (e.g., credentials.json not found): {e}")
    except ValueError as e:
        logger.error(f"Initialization error (e.g., invalid sheet URL): {e}")
    except Exception as e:
        logger.error(f"An unexpected error in main_debug_entry: {e}", exc_info=True)
    finally:
        if sheet_service_instance:
            logger.info("Shutting down sheet service from DEBUG script...")
            await sheet_service_instance.close()
        logger.info("DEBUG script finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main_debug_entry())
    except KeyboardInterrupt:
        logger.info("DEBUG script interrupted by user.")
    except Exception as e:
        logger.critical(f"Critical error during asyncio.run in DEBUG: {e}", exc_info=True)