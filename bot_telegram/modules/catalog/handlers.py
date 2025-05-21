# robotiaga-perfumeshopnew/bot_telegram/modules/catalog/handlers.py
import logging
import math
from aiogram import Router, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database import AsyncSheetServiceWithQueue
from bot_telegram.states.user_interaction_states import CatalogNavigation
from bot_telegram.utils.callback_data_factory import NavigationCallback, PaginationCallback
from bot_telegram.bot_config import ITEMS_PER_PAGE  # Убедитесь, что есть и корректна
from .keyboards import (
    get_categories_keyboard,
    get_products_in_category_keyboard,
    get_product_details_placeholder_keyboard,  # Добавлено
)
from bot_telegram.modules.user_management.handlers import send_or_edit_main_menu  # Для кнопки "В главное меню"

logger = logging.getLogger(__name__)
catalog_router = Router()


# --- Утилита для отправки/редактирования сообщений ---
async def send_or_edit_message(
        target: Message | CallbackQuery,
        text: str,
        reply_markup: types.InlineKeyboardMarkup | types.ReplyKeyboardMarkup | None = None,
        delete_old: bool = False
):
    """Отправляет новое сообщение или редактирует существующее."""
    message_to_edit: Optional[Message] = None
    chat_id = target.from_user.id

    if isinstance(target, CallbackQuery):
        if target.message:
            message_to_edit = target.message
        await target.answer()  # Отвечаем на callback в любом случае
    elif isinstance(target, Message):
        message_to_edit = target  # Если это Message, то мы можем только отправить новое или "ответить"

    if message_to_edit and not delete_old:
        try:
            if message_to_edit.photo and reply_markup:  # Если было фото, а новое - текст с инлайн-клавой
                await message_to_edit.delete()
                await target.bot.send_message(chat_id, text, reply_markup=reply_markup)
                return
            elif message_to_edit.text:  # Если было текстовое
                await message_to_edit.edit_text(text, reply_markup=reply_markup)
                return
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                logger.debug("Message not modified, skipping edit.")
                return  # Ничего не делаем, если сообщение не изменилось
            elif "message to edit not found" in str(e).lower():
                logger.warning("Message to edit not found, sending new one.")
            else:  # Другая ошибка редактирования
                logger.warning(f"Failed to edit message ({e}), sending new one.")
        except Exception as e:  # Другая ошибка
            logger.error(f"Error editing message ({e}), sending new one.")

    # Отправляем новое сообщение, если редактирование не удалось или не предполагалось
    if isinstance(target, Message) and delete_old:  # Если это было сообщение и его нужно удалить
        try:
            await target.delete()
        except Exception:
            pass  # Не страшно, если не удалилось

    await target.bot.send_message(chat_id, text, reply_markup=reply_markup)


# --- Отображение списка категорий ---
async def show_categories_list(target: Message | CallbackQuery, state: FSMContext,
                               sheet_service: AsyncSheetServiceWithQueue):
    await state.set_state(CatalogNavigation.choosing_category)
    logger.info(f"User {target.from_user.id} choosing category.")

    all_products = await sheet_service.get_data_from_cache("Товары")
    if not all_products:
        await send_or_edit_message(
            target,
            "К сожалению, каталог товаров сейчас пуст.",
            reply_markup=InlineKeyboardBuilder().button(text="⬅️ В главное меню", callback_data=NavigationCallback(
                to="main_menu").pack()).as_markup()
        )
        return

    categories = sorted(list(set(p.get("category") for p in all_products if p.get("category"))))
    if not categories:
        await send_or_edit_message(
            target,
            "Категории товаров не найдены.",
            reply_markup=InlineKeyboardBuilder().button(text="⬅️ В главное меню", callback_data=NavigationCallback(
                to="main_menu").pack()).as_markup()
        )
        return

    await send_or_edit_message(target, "Выберите категорию:", get_categories_keyboard(categories))


# Вход в каталог из главного меню
@catalog_router.callback_query(NavigationCallback.filter(F.to == "catalog"), StateFilter(None))
async def handle_catalog_entry(query: CallbackQuery, state: FSMContext, sheet_service: AsyncSheetServiceWithQueue):
    await show_categories_list(query, state, sheet_service)


# Возврат к списку категорий (например, из списка товаров)
@catalog_router.callback_query(NavigationCallback.filter(F.to == "catalog"), CatalogNavigation.viewing_products)
async def handle_back_to_categories_list(query: CallbackQuery, state: FSMContext,
                                         sheet_service: AsyncSheetServiceWithQueue):
    await show_categories_list(query, state, sheet_service)


# --- Отображение товаров в категории ---
async def show_products_page(
        target: CallbackQuery,  # Всегда CallbackQuery для этого
        category_name: str,
        page: int,
        state: FSMContext,
        sheet_service: AsyncSheetServiceWithQueue,
):
    await state.set_state(CatalogNavigation.viewing_products)
    await state.update_data(current_category=category_name, current_page_in_category=page)
    logger.info(f"User {target.from_user.id} viewing category '{category_name}', page {page}.")

    # Получаем все товары этой категории (sheet_service вернет уже отфильтрованные)
    all_products_in_cat = await sheet_service.read_rows_from_cache(
        "Товары", filter_criteria={"category": category_name}
    )

    # Дополнительная фильтрация, если нужна (например, по статусу "Доступен" или "Активен")
    # По ТЗ: "Если флакон полностью забронирован, отображается статус «Забронирован» и недоступен для заказа."
    # Это будет учтено при формировании кнопки товара или на странице деталей. Для списка покажем все.
    # Сортировка
    products_to_display = sorted(all_products_in_cat, key=lambda p: p.get("product_name", "").lower())

    if not products_to_display:
        text = f"В категории '{category_name}' пока нет товаров."
        # Клавиатура для возврата
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="⏪ К категориям", callback_data=NavigationCallback(to="catalog").pack()))
        reply_markup = builder.as_markup()
    else:
        total_items = len(products_to_display)
        total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
        page = max(1, min(page, total_pages))  # Коррекция номера страницы, если он вышел за пределы

        start_index = (page - 1) * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE
        products_on_page = products_to_display[start_index:end_index]

        text = f"Категория: {category_name} (стр. {page}/{total_pages})\nВыберите товар:"
        reply_markup = get_products_in_category_keyboard(
            category_name, products_on_page, page, total_pages
        )

    await send_or_edit_message(target, text, reply_markup)


# Выбор категории -> показать товары
@catalog_router.callback_query(
    NavigationCallback.filter(F.to == "category_selected"),
    CatalogNavigation.choosing_category,
)
async def handle_category_selection(
        query: CallbackQuery,
        callback_data: NavigationCallback,
        state: FSMContext,
        sheet_service: AsyncSheetServiceWithQueue,
):
    category_name = callback_data.category_name
    page = callback_data.page or 1
    if category_name:
        await show_products_page(query, category_name, page, state, sheet_service)
    else:
        # Этого не должно случиться, если callback_data корректен
        await query.answer("Ошибка: категория не указана.", show_alert=True)
        await show_categories_list(query, state, sheet_service)  # Вернуть к выбору категорий


# Пагинация товаров
@catalog_router.callback_query(
    PaginationCallback.filter(F.context == "catalog_category"),
    CatalogNavigation.viewing_products,
)
async def handle_products_list_pagination(
        query: CallbackQuery,
        callback_data: PaginationCallback,
        state: FSMContext,
        sheet_service: AsyncSheetServiceWithQueue,
):
    category_name = callback_data.category_name
    target_page = callback_data.target_page
    if not category_name:  # Должен быть в callback_data
        fsm_data = await state.get_data()  # Попробуем извлечь из состояния, если есть
        category_name = fsm_data.get("current_category")

    if category_name and target_page:
        await show_products_page(query, category_name, target_page, state, sheet_service)
    else:
        await query.answer("Ошибка пагинации: не удалось определить категорию или страницу.", show_alert=True)
        await show_categories_list(query, state, sheet_service)  # Откатиться к списку категорий


# --- Обработка нажатия на товар (переход к деталям - заглушка) ---
# robotiaga-perfumeshopnew/bot_telegram/modules/catalog/handlers.py
# ... другие импорты ...
# Убираем get_product_details_placeholder_keyboard из импортов .keyboards, если он там был только для заглушки

# Импортируем функцию показа деталей товара
from bot_telegram.modules.product_details.handlers import show_product_details_view


# --- Обработка нажатия на товар (переход к деталям - НЕ заглушка) ---
@catalog_router.callback_query(
    NavigationCallback.filter(F.to == "product_details"),
    CatalogNavigation.viewing_products,
)
async def handle_product_selection_from_catalog(  # Переименовал для ясности
        query: CallbackQuery,
        callback_data: NavigationCallback,
        state: FSMContext,
        sheet_service: AsyncSheetServiceWithQueue
):
    product_id = callback_data.product_id
    category_for_back = callback_data.category_for_back
    page_for_back = callback_data.catalog_page_for_back

    if product_id is None or category_for_back is None or page_for_back is None:
        await query.answer("Ошибка: не удалось определить товар или данные для возврата.", show_alert=True)
        await show_categories_list(query, state, sheet_service)
        return

    # Сохраняем данные для кнопки "назад" в состояние FSM перед переходом
    await state.update_data(
        category_for_back=category_for_back,
        catalog_page_for_back=page_for_back
    )

    # Вызываем функцию из модуля product_details
    await show_product_details_view(query, product_id, sheet_service, state)


# Возврат в главное меню из любого состояния каталога
@catalog_router.callback_query(
    NavigationCallback.filter(F.to == "main_menu"),
    StateFilter(CatalogNavigation)  # Любое состояние из группы CatalogNavigation
)
async def handle_catalog_to_main_menu(query: CallbackQuery, state: FSMContext):
    logger.info(f"User {query.from_user.id} navigating to main menu from catalog state {await state.get_state()}.")
    await send_or_edit_main_menu(query, state)  # Используем функцию из user_management


# Обработка "ignore" callback для кнопок, которые не должны ничего делать (например, отображение номера страницы)
@catalog_router.callback_query(F.data == "ignore_page_display")
async def handle_ignore_callback(query: CallbackQuery):
    await query.answer()