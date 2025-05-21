# bot_telegram/bot_main.py
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot_telegram.bot_config import BOT_TOKEN
from app.database import AsyncSheetServiceWithQueue
from config import GOOGLE_SHEET_URL, CREDENTIALS_JSON_PATH

# Импортируем роутеры
from bot_telegram.modules.user_management.handlers import user_router
from bot_telegram.modules.catalog.handlers import catalog_router # ДОБАВЛЕН ИМПОРТ
from bot_telegram.modules.product_details.handlers import product_details_router
# from bot_telegram.modules.cart.handlers import cart_routerф

logger = logging.getLogger(__name__)

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d [%(name)s] - %(message)s",
    )
    logger.info("Starting bot...")

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.critical("No BOT_TOKEN provided or placeholder detected. Exiting.")
        return

    sheet_service = AsyncSheetServiceWithQueue(
        sheet_url=GOOGLE_SHEET_URL,
        credentials_path=CREDENTIALS_JSON_PATH
    )
    try:
        await sheet_service.start_services()
        logger.info("Sheet service initialized and background tasks started for bot.")

        storage = MemoryStorage()
        default_properties = DefaultBotProperties(parse_mode="HTML")
        bot = Bot(token=BOT_TOKEN, default=default_properties)

        # Передаем sheet_service в Dispatcher, чтобы он был доступен в хэндлерах через аргументы
        # или через data['sheet_service'] если используется middleware
        dp = Dispatcher(storage=storage, sheet_service=sheet_service)

        # Порядок регистрации роутеров может быть важен, если есть пересекающиеся фильтры
        # User router обычно содержит общие команды типа /start, /help
        dp.include_router(user_router)
        # Catalog router для навигации по каталогу
        dp.include_router(catalog_router) # ДОБАВЛЕНА РЕГИСТРАЦИЯ
        dp.include_router(product_details_router)
        # ... другие роутеры ...


        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Bot polling started.")
        await dp.start_polling(bot)

    except Exception as e:
        logger.critical(f"Critical error in bot_main: {e}", exc_info=True)
    finally:
        if 'sheet_service' in locals() and sheet_service:
            logger.info("Shutting down sheet_service from bot_main...")
            await sheet_service.close()
        if 'dp' in locals() and hasattr(dp, 'fsm') and dp.fsm.storage:
            logger.info("Closing FSM storage...")
            await dp.fsm.storage.close()
        if 'bot' in locals() and hasattr(bot, 'session') and bot.session:
            logger.info("Closing bot session...")
            await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.critical(f"Unhandled exception in asyncio.run(main()): {e}", exc_info=True)