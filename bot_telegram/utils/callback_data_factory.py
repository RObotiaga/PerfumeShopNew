# bot_telegram/utils/callback_data_factory.py
from aiogram.filters.callback_data import CallbackData


class UserAgreementCallback(CallbackData, prefix="user_agr"):
    action: str  # "accept" или "view"


class NavigationCallback(CallbackData, prefix="nav"):
    to: str  # "catalog", "cart", "main_menu", "category", "product", "page"
    category_name: str | None = None
    product_id: int | None = None
    page: int | None = None
    # Можно добавить параметр для сохранения текущей страницы каталога при переходе к товару
    # для корректной кнопки "Назад"
    catalog_page_for_back: int | None = None
    category_for_back: str | None = None


class ProductActionCallback(CallbackData, prefix="prod_act"):
    action: str  # "add_to_cart", "change_qty", "go_to_cart", "back_to_list"
    product_id: int
    # Для change_qty:
    current_qty: float | None = None  # Текущее количество в корзине
    change_value: float | str | None = (
        None  # На сколько изменить (+1, -1, +2.5, "clear_volume")
    )
    # Для кнопки назад из карточки товара в список товаров
    catalog_page_for_back: int | None = None
    category_for_back: str | None = None


class CartActionCallback(CallbackData, prefix="cart_act"):
    action: str  # "change_item_qty", "remove_item", "checkout", "clear_cart", "continue_shopping"
    product_id: int | None = None  # Для действий с конкретным товаром в корзине
    # Для change_item_qty:
    current_qty: float | None = None
    change_value: float | str | None = None


# Добавим сюда другие фабрики по мере необходимости (например, для пагинации)
class PaginationCallback(CallbackData, prefix="paginate"):
    action: str  # "prev", "next", "to_page"
    target_page: int
    category_name: str | None = None  # Для пагинации внутри категории
    # Можно добавить другие параметры, идентифицирующие контекст пагинации
