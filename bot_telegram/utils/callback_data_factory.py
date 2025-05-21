# robotiaga-perfumeshopnew/bot_telegram/utils/callback_data_factory.py
from aiogram.filters.callback_data import CallbackData


class UserAgreementCallback(CallbackData, prefix="user_agr"):
    action: str  # "accept"


class NavigationCallback(CallbackData, prefix="nav"):
    to: str  # "catalog", "cart", "main_menu", "my_orders", "info", "help",
    # "category_selected", "product_details" # ДОБАВЛЕНЫ значения для ясности
    category_name: str | None = None
    product_id: int | None = None  # Добавлено для перехода к товару
    page: int | None = None
    catalog_page_for_back: int | None = (
        None  # Для возврата из карточки товара в каталог
    )
    category_for_back: str | None = None  # Для возврата из карточки товара в каталог


class ProductActionCallback(CallbackData, prefix="prod_act"):
    action: str  # "select_volume", "add_to_cart", "remove_from_cart_details_view", etc.
    product_id: int
    # Для select_volume и add_to_cart:
    change_value: float | str | None = None  # выбранный объем или кол-во для добавления
    # current_qty УБРАНО, так как оно больше для отображения, чем для действия.
    # category_for_back УБРАНО - будем брать из FSM
    # catalog_page_for_back УБРАНО - будем брать из FSM


class CartActionCallback(CallbackData, prefix="cart_act"):
    # Для действий в корзине, пока не трогаем
    action: str
    product_id: int | None = None
    current_qty: float | None = None
    change_value: float | str | None = None


class PaginationCallback(CallbackData, prefix="paginate"):
    action: str  # "prev", "next" (to_page можно убрать если не используется напрямую)
    target_page: int
    context: str  # например "catalog_category"
    category_name: str | None = None
