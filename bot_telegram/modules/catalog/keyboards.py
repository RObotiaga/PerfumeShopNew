# robotiaga-perfumeshopnew/bot_telegram/modules/catalog/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict

from bot_telegram.utils.callback_data_factory import NavigationCallback, PaginationCallback
from bot_telegram.bot_config import (
    PRODUCT_STATUS_EMOJI,
    DEFAULT_PRODUCT_EMOJI,
    ITEMS_PER_PAGE, # Убедитесь, что эта константа есть и корректна
)

def get_categories_keyboard(categories: List[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category_name in categories:
        builder.row(
            InlineKeyboardButton(
                text=category_name,
                callback_data=NavigationCallback(
                    to="category_selected", category_name=category_name, page=1
                ).pack(),
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ В главное меню",
            callback_data=NavigationCallback(to="main_menu").pack(),
        )
    )
    return builder.as_markup()


def get_products_in_category_keyboard(
    category_name: str, products_on_page: List[Dict], current_page: int, total_pages: int
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if not products_on_page:
        builder.row(
            InlineKeyboardButton(text="Товаров не найдено", callback_data="ignore")
        ) # 'ignore' - это заглушка, можно обработать или сделать другой коллбэк
    else:
        for product in products_on_page:
            status_raw = product.get("status", "").lower()
            status_emoji = PRODUCT_STATUS_EMOJI.get(status_raw, DEFAULT_PRODUCT_EMOJI)

            name = product.get("product_name", "N/A")
            price_val = product.get("price_per_unit")
            price_str = (
                f"{price_val:.0f} ₽"
                if isinstance(price_val, (float, int))
                else "Цена?"
            ) # Убрал 'руб.' для краткости

            # Текст кнопки как в примере (статус, имя, цена)
            # В примере еще было quantity_text, но это доступное количество, а не в корзине.
            # Пока оставим без него для краткости кнопки.
            button_text = f"{status_emoji} {name} - {price_str}"

            builder.row(
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=NavigationCallback(
                        to="product_details", # Переход к детальному просмотру товара
                        product_id=int(product.get("product_id")),
                        category_for_back=category_name, # Для кнопки "Назад" в карточке товара
                        catalog_page_for_back=current_page, # Для кнопки "Назад" в карточке товара
                    ).pack(),
                )
            )

    # Кнопки пагинации
    if total_pages > 1:
        pagination_buttons = []
        if current_page > 1:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Пред.",
                    callback_data=PaginationCallback(
                        action="prev",
                        target_page=current_page - 1,
                        context="catalog_category",
                        category_name=category_name,
                    ).pack(),
                )
            )
        pagination_buttons.append(
            InlineKeyboardButton(
                text=f"{current_page}/{total_pages}", callback_data="ignore_page_display" # noop
            )
        )
        if current_page < total_pages:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="След. ➡️",
                    callback_data=PaginationCallback(
                        action="next",
                        target_page=current_page + 1,
                        context="catalog_category",
                        category_name=category_name,
                    ).pack(),
                )
            )
        builder.row(*pagination_buttons)

    builder.row(
        InlineKeyboardButton(
            text="⏪ К категориям",
            callback_data=NavigationCallback(to="catalog").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏠 В главное меню",
            callback_data=NavigationCallback(to="main_menu").pack(),
        )
    )
    return builder.as_markup()

# Клавиатура для детального просмотра товара (пока очень простая, будет в product_details)
def get_product_details_placeholder_keyboard(category_name_for_back: str, catalog_page_for_back: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Кнопка "Назад к списку товаров"
    builder.row(
        InlineKeyboardButton(
            text="⬅️ К списку товаров",
            callback_data=NavigationCallback(
                to="category_selected", # Возвращает к списку товаров той же категории
                category_name=category_name_for_back,
                page=catalog_page_for_back
            ).pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏠 В главное меню",
            callback_data=NavigationCallback(to="main_menu").pack()
        )
    )
    return builder.as_markup()