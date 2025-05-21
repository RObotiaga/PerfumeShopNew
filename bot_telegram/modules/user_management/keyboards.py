 # bot_telegram/modules/user_management/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton # ReplyKeyboardMarkup, KeyboardButton УДАЛЕНЫ, если не нужны где-то еще
from aiogram.utils.keyboard import InlineKeyboardBuilder # ReplyKeyboardBuilder УДАЛЕН

from bot_telegram.utils.callback_data_factory import UserAgreementCallback, NavigationCallback # ДОБАВЛЕН NavigationCallback
from bot_telegram.bot_config import BUTTON_TEXT_AGREE, BUTTON_TEXT_VIEW_AGREEMENT, USER_AGREEMENT_URL

def get_agreement_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=BUTTON_TEXT_VIEW_AGREEMENT,
            url=USER_AGREEMENT_URL
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=BUTTON_TEXT_AGREE,
            callback_data=UserAgreementCallback(action="accept").pack()
        )
    )
    return builder.as_markup()

def get_main_menu_keyboard() -> InlineKeyboardMarkup: # ИЗМЕНЕНО: возвращает InlineKeyboardMarkup
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🛍️ Каталог", callback_data=NavigationCallback(to="catalog").pack()),
        InlineKeyboardButton(text="🛒 Корзина", callback_data=NavigationCallback(to="cart").pack())
    )
    builder.row(
        InlineKeyboardButton(text="📦 Мои заказы", callback_data=NavigationCallback(to="my_orders").pack()),
        InlineKeyboardButton(text="ℹ️ Информация о магазине", callback_data=NavigationCallback(to="info").pack())
    )
    builder.row(
        InlineKeyboardButton(text="❓ Помощь", callback_data=NavigationCallback(to="help").pack())
    )
    return builder.as_markup()

