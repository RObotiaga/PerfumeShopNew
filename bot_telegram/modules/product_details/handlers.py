# robotiaga-perfumeshopnew/bot_telegram/modules/product_details/handlers.py
import logging
from typing import Optional, Dict, Union
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from app.database import AsyncSheetServiceWithQueue
from bot_telegram.states.user_interaction_states import CatalogNavigation
from bot_telegram.utils.callback_data_factory import (
    NavigationCallback,
    ProductActionCallback,
)
from .keyboards import get_product_details_keyboard
from bot_telegram.bot_config import PRODUCT_STATUS_EMOJI, DEFAULT_PRODUCT_EMOJI

# Импортируем send_or_edit_message, show_categories_list и show_products_page из catalog.handlers
from bot_telegram.modules.catalog.handlers import (
    send_or_edit_message,
    show_categories_list,
    show_products_page,
)

logger = logging.getLogger(__name__)
product_details_router = Router()


# --- Вспомогательная функция для форматирования описания товара ---
def format_product_message_text(
    product_data: Dict, current_quantity_in_cart: float = 0.0
) -> str:
    name = product_data.get("product_name", "N/A")
    description = product_data.get("description", "Описание отсутствует.")
    price_per_unit = product_data.get("price_per_unit", 0.0)
    unit = product_data.get("unit_of_measure", "шт")
    available_quantity_gs = product_data.get("available_quantity", 0.0)
    status_raw = product_data.get("status", "").lower()
    status_emoji = PRODUCT_STATUS_EMOJI.get(status_raw, DEFAULT_PRODUCT_EMOJI)
    product_type = product_data.get("product_type", "Штучный")

    price_text = (
        f"{price_per_unit:.2f} ₽ / {unit}" if price_per_unit > 0 else "Цена по запросу"
    )

    text = f"<b>{name}</b> {status_emoji}\n\n"
    text += f"{description}\n\n"
    text += f"Цена: {price_text}\n"

    if product_type == "Объемный":
        text += f"Доступно на складе: {available_quantity_gs:.2f} {unit}\n"
        if current_quantity_in_cart > 0:
            total_cart_item_price = price_per_unit * current_quantity_in_cart
            text += f"Уже в корзине: {current_quantity_in_cart} {unit} (<b>{total_cart_item_price:.2f} ₽</b>)\n"
    else:  # Штучный
        text += f"Доступно на складе: {int(available_quantity_gs)} {unit}\n"
        if current_quantity_in_cart > 0:
            total_cart_item_price = price_per_unit * int(current_quantity_in_cart)
            text += f"Уже в корзине: {int(current_quantity_in_cart)} {unit} (<b>{total_cart_item_price:.2f} ₽</b>)\n"

    return text


# --- Основная функция отображения деталей товара ---
async def show_product_details_view(
    target: CallbackQuery,
    product_id: int,
    sheet_service: AsyncSheetServiceWithQueue,
    state: FSMContext,
    show_action_feedback: Optional[str] = None,
):
    await state.set_state(CatalogNavigation.viewing_product_detail)

    product_list = await sheet_service.read_rows_from_cache(
        "Товары", filter_criteria={"product_id": product_id}
    )
    if not product_list:
        await send_or_edit_message(target, "Товар не найден.", reply_markup=None)
        return

    product_data = product_list[0]
    # Сохраняем только ID текущего товара, его данные будем брать из sheet_service если нужно
    await state.update_data(current_product_id=product_id)

    # --- Логика корзины (FSMContext) ---
    user_fsm_data = await state.get_data()
    cart = user_fsm_data.get("cart", {})
    # Получаем текущее количество ЭТОГО товара в корзине
    current_quantity_this_item_in_cart = cart.get(str(product_id), {}).get(
        "quantity", 0.0
    )
    # --- Конец логики корзины ---

    message_text = format_product_message_text(
        product_data, current_quantity_this_item_in_cart
    )
    if show_action_feedback:
        message_text = f"{show_action_feedback}\n\n" + message_text

    fsm_data = await state.get_data()
    category_for_back = fsm_data.get("category_for_back", "Каталог")
    catalog_page_for_back = fsm_data.get("catalog_page_for_back", 1)

    reply_markup = get_product_details_keyboard(
        product_data,
        category_for_back,
        catalog_page_for_back,
        current_quantity_in_cart=current_quantity_this_item_in_cart,
    )

    photo_url = product_data.get("photo_url")
    current_message = target.message

    if photo_url:
        if current_message.photo:
            try:
                await current_message.edit_caption(
                    caption=message_text, reply_markup=reply_markup
                )
            except TelegramBadRequest as e_caption:
                if "message is not modified" not in str(e_caption).lower():
                    logger.warning(
                        f"Failed to edit caption ({e_caption}), attempting delete and send for photo"
                    )
                    await current_message.delete()
                    await target.bot.send_photo(
                        chat_id=target.from_user.id,
                        photo=photo_url,
                        caption=message_text,
                        reply_markup=reply_markup,
                    )
                elif current_message.reply_markup != reply_markup:
                    try:
                        await current_message.edit_reply_markup(
                            reply_markup=reply_markup
                        )
                    except TelegramBadRequest:
                        pass
        else:
            await current_message.delete()
            await target.bot.send_photo(
                chat_id=target.from_user.id,
                photo=photo_url,
                caption=message_text,
                reply_markup=reply_markup,
            )
    else:
        if current_message.photo:
            await current_message.delete()
            await target.bot.send_message(
                chat_id=target.from_user.id,
                text=message_text,
                reply_markup=reply_markup,
            )
        else:
            await send_or_edit_message(target, message_text, reply_markup)


# --- Обработчики действий ---


# Вход на страницу деталей товара (из каталога)
@product_details_router.callback_query(
    NavigationCallback.filter(F.to == "product_details")
)
async def product_details_entry(
    query: CallbackQuery,
    callback_data: NavigationCallback,
    state: FSMContext,
    sheet_service: AsyncSheetServiceWithQueue,
):
    await state.update_data(
        category_for_back=callback_data.category_for_back,
        catalog_page_for_back=callback_data.catalog_page_for_back,
    )
    await show_product_details_view(
        query, callback_data.product_id, sheet_service, state
    )


# --- Новые обработчики для управления количеством в корзине из карточки товара ---


async def _update_cart_and_redraw(
    query: CallbackQuery,
    product_id: int,
    new_quantity_in_cart: float,
    product_data: Dict,
    state: FSMContext,
    sheet_service: AsyncSheetServiceWithQueue,
    action_feedback: str,
):
    user_fsm_data = await state.get_data()
    cart = user_fsm_data.get("cart", {})

    if new_quantity_in_cart > 0:
        cart[str(product_id)] = {
            "quantity": new_quantity_in_cart,
            "name": product_data.get("product_name"),
            "price_per_unit": product_data.get("price_per_unit"),
            "unit": product_data.get("unit_of_measure"),
            "type": product_data.get("product_type"),
        }
    else:
        if str(product_id) in cart:
            del cart[str(product_id)]

    await state.update_data(cart=cart)
    logger.info(
        f"User {query.from_user.id} cart updated for product {product_id}: {cart.get(str(product_id))}"
    )

    await show_product_details_view(
        query, product_id, sheet_service, state, show_action_feedback=action_feedback
    )


@product_details_router.callback_query(
    ProductActionCallback.filter(F.action == "increase_volume_in_cart"),
    CatalogNavigation.viewing_product_detail,
)
async def handle_increase_volume(
    query: CallbackQuery,
    callback_data: ProductActionCallback,
    state: FSMContext,
    sheet_service: AsyncSheetServiceWithQueue,
):
    product_id = callback_data.product_id
    volume_step_to_add = float(callback_data.change_value)

    product_list = await sheet_service.read_rows_from_cache(
        "Товары", filter_criteria={"product_id": product_id}
    )
    if not product_list:
        await query.answer("Товар не найден!", show_alert=True)
        return
    product_data = product_list[0]
    available_quantity_gs = product_data.get("available_quantity", 0.0)

    user_fsm_data = await state.get_data()
    cart = user_fsm_data.get("cart", {})
    current_qty_in_cart = cart.get(str(product_id), {}).get("quantity", 0.0)

    if current_qty_in_cart + volume_step_to_add > available_quantity_gs:
        await query.answer(
            f"Нельзя добавить больше {available_quantity_gs} мл.", show_alert=True
        )
        return

    new_total_quantity = current_qty_in_cart + volume_step_to_add
    feedback = f"✅ Добавлено {volume_step_to_add} мл."
    await _update_cart_and_redraw(
        query,
        product_id,
        new_total_quantity,
        product_data,
        state,
        sheet_service,
        feedback,
    )


@product_details_router.callback_query(
    ProductActionCallback.filter(F.action == "reset_volume_in_cart"),
    CatalogNavigation.viewing_product_detail,
)
async def handle_reset_volume(
    query: CallbackQuery,
    callback_data: ProductActionCallback,
    state: FSMContext,
    sheet_service: AsyncSheetServiceWithQueue,
):
    product_id = callback_data.product_id
    product_list = await sheet_service.read_rows_from_cache(
        "Товары", filter_criteria={"product_id": product_id}
    )
    if not product_list:
        await query.answer("Товар не найден!", show_alert=True)
        return

    feedback = "🗑️ Объем в корзине сброшен."
    await _update_cart_and_redraw(
        query, product_id, 0.0, product_list[0], state, sheet_service, feedback
    )


# Новые обработчики для управления количеством ШТУЧНЫХ товаров
@product_details_router.callback_query(
    ProductActionCallback.filter(
        F.action.in_(
            {"increase_pcs_in_cart", "decrease_pcs_from_cart", "reset_pcs_in_cart"}
        )
    ),
    CatalogNavigation.viewing_product_detail,
)
async def handle_pcs_quantity_change(
    query: CallbackQuery,
    callback_data: ProductActionCallback,
    state: FSMContext,
    sheet_service: AsyncSheetServiceWithQueue,
):
    product_id = callback_data.product_id
    action = callback_data.action

    change_value_from_cb = (
        callback_data.change_value
    )  # Это будет шаг (1, 10, или remaining_available) или None для reset
    step_quantity = 0
    if change_value_from_cb is not None:
        try:
            step_quantity = int(float(change_value_from_cb))
        except ValueError:
            logger.error(
                f"Invalid step_quantity for PCS item {product_id}: {change_value_from_cb}"
            )
            await query.answer("Ошибка изменения количества.", show_alert=True)
            return

    product_list = await sheet_service.read_rows_from_cache(
        "Товары", filter_criteria={"product_id": product_id}
    )
    if not product_list:
        await query.answer("Товар не найден!", show_alert=True)
        return
    product_data = product_list[0]
    available_quantity_gs = int(product_data.get("available_quantity", 0))

    user_fsm_data = await state.get_data()
    cart = user_fsm_data.get("cart", {})
    current_qty_in_cart = int(cart.get(str(product_id), {}).get("quantity", 0))

    new_total_quantity_in_cart = current_qty_in_cart
    feedback_message = ""

    if action == "increase_pcs_in_cart":
        if step_quantity <= 0:  # Шаг должен быть положительным
            await query.answer("Некорректный шаг увеличения.", show_alert=True)
            return

        if current_qty_in_cart + step_quantity <= available_quantity_gs:
            new_total_quantity_in_cart = current_qty_in_cart + step_quantity
            feedback_message = f"✅ Добавлено {step_quantity} шт."
        else:
            # Если шаг больше, чем можно добавить, добавляем максимально возможное количество
            can_add = available_quantity_gs - current_qty_in_cart
            if can_add > 0:
                new_total_quantity_in_cart = current_qty_in_cart + can_add
                feedback_message = f"✅ Добавлено {can_add} шт. (максимум доступно)"
            else:
                await query.answer(
                    f"Больше добавить нельзя. В наличии: {available_quantity_gs} шт.",
                    show_alert=True,
                )
                return

    elif action == "decrease_pcs_from_cart":
        if step_quantity <= 0:  # Шаг должен быть положительным
            await query.answer("Некорректный шаг уменьшения.", show_alert=True)
            return

        if current_qty_in_cart >= step_quantity:
            new_total_quantity_in_cart = current_qty_in_cart - step_quantity
            feedback_message = f"🗑️ Убрано {step_quantity} шт."
            if new_total_quantity_in_cart == 0:
                feedback_message = "🗑️ Товар полностью убран из корзины."
        else:  # Пытаемся убрать больше, чем есть
            if current_qty_in_cart > 0:
                new_total_quantity_in_cart = 0  # Убираем всё
                feedback_message = (
                    f"🗑️ Убрано {current_qty_in_cart} шт. (всё из корзины)."
                )
            else:  # Уже 0 в корзине
                await query.answer("Этого товара нет в корзине.", show_alert=False)
                return

    elif action == "reset_pcs_in_cart":
        if current_qty_in_cart > 0:
            new_total_quantity_in_cart = 0
            feedback_message = "🔄 Количество в корзине сброшено."
        else:
            await query.answer("Товара и так нет в корзине.", show_alert=False)
            return  # Ничего не делаем и не перерисовываем

    await _update_cart_and_redraw(
        query,
        product_id,
        float(new_total_quantity_in_cart),  # _update_cart_and_redraw ожидает float
        product_data,
        state,
        sheet_service,
        feedback_message,
    )


# --- Обработчик кнопки "К списку товаров" ---
@product_details_router.callback_query(
    NavigationCallback.filter(F.to == "category_selected"),
    CatalogNavigation.viewing_product_detail,
)
async def handle_back_to_product_list_from_details(
    query: CallbackQuery,
    callback_data: NavigationCallback,
    state: FSMContext,
    sheet_service: AsyncSheetServiceWithQueue,
):
    category_name = callback_data.category_name
    page = callback_data.page or 1

    if not category_name:
        logger.error(
            "Cannot go back to product list: category_name is missing in callback_data."
        )
        await query.answer(
            "Ошибка: не удалось определить категорию для возврата.", show_alert=True
        )
        await show_categories_list(query, state, sheet_service)
        return

    logger.info(
        f"User {query.from_user.id} going back to product list: category '{category_name}', page {page}"
    )

    await show_products_page(query, category_name, page, state, sheet_service)


@product_details_router.callback_query(F.data.startswith("ignore_"))
async def handle_ignore_pd_callback(query: CallbackQuery):
    await query.answer()
