 # bot_telegram/modules/user_management/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from bot_telegram.utils.callback_data_factory import UserAgreementCallback, NavigationCallback
from bot_telegram.bot_config import BUTTON_TEXT_AGREE, BUTTON_TEXT_VIEW_AGREEMENT

def get_agreement_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=BUTTON_TEXT_VIEW_AGREEMENT,
            callback_data=UserAgreementCallback(action="view").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=BUTTON_TEXT_AGREE,
            callback_data=UserAgreementCallback(action="accept").pack()
        )
    )
    return builder.as_markup()

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🛍️ Каталог"),
        KeyboardButton(text="🛒 Корзина")
    )
    builder.row(
        KeyboardButton(text="📦 Мои заказы"),
        KeyboardButton(text="ℹ️ Информация о магазине")
    )
    builder.row(
        KeyboardButton(text="❓ Помощь") # Связаться с менеджером
    )
    return builder.as_markup(resize_keyboard=True)

def get_view_agreement_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для сообщения с текстом соглашения, кнопка Назад к выбору"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⬅️ Назад",
        callback_data=UserAgreementCallback(action="back_to_options").pack()
    )
    return builder.as_markup()