# robotiaga-perfumeshopnew/bot_telegram/modules/product_details/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import Dict, Any, List, Optional
import logging  # Добавим логгер

from bot_telegram.utils.callback_data_factory import (
    NavigationCallback,
    ProductActionCallback,
)
from bot_telegram.bot_config import DEFAULT_PORTION_STEPS

logger = logging.getLogger(__name__)  # Инициализируем логгер


def get_product_details_keyboard(
    product_data: Dict[str, Any],
    category_for_back: str,
    catalog_page_for_back: int,
    current_quantity_in_cart: float = 0.0,  # Для штучных это будет int, но тип float для унификации
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    product_id = int(product_data.get("product_id"))
    status = product_data.get("status", "").lower()
    product_type = product_data.get("product_type", "Штучный")
    available_quantity_gs = product_data.get("available_quantity", 0.0)

    is_in_cart_flag = current_quantity_in_cart > 0
    current_qty_int_for_pcs = int(current_quantity_in_cart)

    # 1. Кнопки управления количеством для ОБЪЕМНЫХ товаров
    if product_type == "Объемный" and status != "забронирован":
        if is_in_cart_flag:
            builder.row(
                InlineKeyboardButton(
                    text=f"В корзине: {current_quantity_in_cart} мл. Сбросить 🔄",
                    callback_data=ProductActionCallback(
                        action="reset_volume_in_cart",
                        product_id=product_id,
                    ).pack(),
                )
            )
        else:
            builder.row(
                InlineKeyboardButton(
                    text="В корзине: 0 мл", callback_data="ignore_cart_qty_display"
                )
            )

        if available_quantity_gs > 0:
            order_steps_from_sheet_str = product_data.get("order_step", "")
            raspil_type_from_sheet = product_data.get("portion_type", "Обычный")

            actual_steps: List[float] = []

            if (
                order_steps_from_sheet_str
                and isinstance(order_steps_from_sheet_str, str)
                and order_steps_from_sheet_str.strip()
            ):
                try:
                    parsed_steps = sorted(
                        list(
                            set(
                                float(s.strip().replace(",", "."))
                                for s in order_steps_from_sheet_str.split(";")
                                if s.strip() and float(s.strip().replace(",", ".")) > 0
                            )
                        )
                    )
                    if parsed_steps:
                        actual_steps = parsed_steps
                        logger.debug(
                            f"Using order_steps from sheet for product {product_id}: {actual_steps}"
                        )
                    else:
                        logger.warning(
                            f"Parsed empty or invalid order_step list from sheet for product {product_id}: '{order_steps_from_sheet_str}'. Falling back to defaults based on raspil_type."
                        )
                except ValueError:
                    logger.warning(
                        f"Invalid format in order_step from sheet for product {product_id}: '{order_steps_from_sheet_str}'. Falling back to defaults based on raspil_type."
                    )

            if not actual_steps:
                actual_steps = DEFAULT_PORTION_STEPS.get(
                    raspil_type_from_sheet,
                    DEFAULT_PORTION_STEPS.get("Обычный", [1.0, 2.0, 3.0, 5.0, 10.0]),
                )
                logger.debug(
                    f"Using default_steps for product {product_id} (raspil_type: {raspil_type_from_sheet}): {actual_steps}"
                )

            volume_buttons_row1, volume_buttons_row2 = [], []
            for step_volume in actual_steps:
                if current_quantity_in_cart + step_volume <= available_quantity_gs:
                    btn = InlineKeyboardButton(
                        text=f"+ {step_volume} мл",
                        callback_data=ProductActionCallback(
                            action="increase_volume_in_cart",
                            product_id=product_id,
                            change_value=step_volume,
                        ).pack(),
                    )
                    if len(volume_buttons_row1) < 3:
                        volume_buttons_row1.append(btn)
                    elif len(volume_buttons_row2) < 3:
                        volume_buttons_row2.append(btn)

            if volume_buttons_row1:
                builder.row(*volume_buttons_row1)
            if volume_buttons_row2:
                builder.row(*volume_buttons_row2)
        elif available_quantity_gs <= 0 and not is_in_cart_flag:
            builder.row(
                InlineKeyboardButton(
                    text="🔴 Нет в наличии", callback_data="ignore_status"
                )
            )

    # 2. Кнопки управления количеством для ШТУЧНЫХ товаров
    elif product_type == "Штучный":
        if status == "забронирован":
            builder.row(
                InlineKeyboardButton(
                    text="🔒 Забронирован", callback_data="ignore_status"
                )
            )
        elif available_quantity_gs <= 0 and not is_in_cart_flag:
            builder.row(
                InlineKeyboardButton(
                    text="🔴 Нет в наличии", callback_data="ignore_status"
                )
            )
        else:
            qty_control_buttons = []
            if current_qty_int_for_pcs >= 10:
                qty_control_buttons.append(
                    InlineKeyboardButton(
                        text="-10",
                        callback_data=ProductActionCallback(
                            action="decrease_pcs_from_cart",
                            product_id=product_id,
                            change_value=10,
                        ).pack(),
                    )
                )
            if current_qty_int_for_pcs >= 1:
                qty_control_buttons.append(
                    InlineKeyboardButton(
                        text="-1",
                        callback_data=ProductActionCallback(
                            action="decrease_pcs_from_cart",
                            product_id=product_id,
                            change_value=1,
                        ).pack(),
                    )
                )

            qty_control_buttons.append(
                InlineKeyboardButton(
                    text=f"{current_qty_int_for_pcs} шт",
                    callback_data="ignore_qty_display",
                )
            )

            remaining_available = available_quantity_gs - current_qty_int_for_pcs
            if remaining_available >= 1:
                qty_control_buttons.append(
                    InlineKeyboardButton(
                        text="+1",
                        callback_data=ProductActionCallback(
                            action="increase_pcs_in_cart",
                            product_id=product_id,
                            change_value=1,
                        ).pack(),
                    )
                )
            if remaining_available >= 10:
                qty_control_buttons.append(
                    InlineKeyboardButton(
                        text="+10",
                        callback_data=ProductActionCallback(
                            action="increase_pcs_in_cart",
                            product_id=product_id,
                            change_value=10,
                        ).pack(),
                    )
                )
            elif remaining_available > 1 and remaining_available < 10:
                qty_control_buttons.append(
                    InlineKeyboardButton(
                        text=f"+{remaining_available}",
                        callback_data=ProductActionCallback(
                            action="increase_pcs_in_cart",
                            product_id=product_id,
                            change_value=remaining_available,
                        ).pack(),
                    )
                )

            if qty_control_buttons:
                builder.row(*qty_control_buttons)

            if is_in_cart_flag and current_qty_int_for_pcs > 0:
                builder.row(
                    InlineKeyboardButton(
                        text="🔄 Сбросить из корзины",
                        callback_data=ProductActionCallback(
                            action="reset_pcs_in_cart", product_id=product_id
                        ).pack(),
                    )
                )

    # 3. Кнопка "Перейти в корзину"
    if is_in_cart_flag:
        builder.row(
            InlineKeyboardButton(
                text="🛒 Перейти в корзину",
                callback_data=NavigationCallback(to="cart").pack(),
            )
        )

    # 4. Навигационные кнопки
    builder.row(
        InlineKeyboardButton(
            text="⬅️ К списку товаров",
            callback_data=NavigationCallback(
                to="category_selected",
                category_name=category_for_back,
                page=catalog_page_for_back,
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏠 В главное меню",
            callback_data=NavigationCallback(to="main_menu").pack(),
        )
    )
    return builder.as_markup()
