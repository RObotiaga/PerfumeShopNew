 # bot_telegram/modules/user_management/handlers.py
import logging
import datetime

from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.database import AsyncSheetServiceWithQueue, User
from bot_telegram.states.user_interaction_states import UserAgreement
from .keyboards import get_agreement_keyboard, get_main_menu_keyboard, get_view_agreement_keyboard
from bot_telegram.utils.callback_data_factory import UserAgreementCallback
from bot_telegram.bot_config import USER_AGREEMENT_PATH

logger = logging.getLogger(__name__)
user_router = Router()

# Предполагается, что sheet_service будет передан в router или доступен через middleware
# Пока что для простоты сделаем его глобальным в этом модуле (не лучший подход для прода)
# В bot_main.py мы передадим его корректно.

async def send_agreement_prompt(message: Message, state: FSMContext, user_exists: bool = False):
    greeting_text = (
        f"Здравствуйте, {message.from_user.full_name}!\n"
        "Добро пожаловать в наш магазин парфюмерии Robotiaga Perfumes!\n\n"
        "Для продолжения, пожалуйста, ознакомьтесь с нашей Политикой обработки персональных данных и примите ее условия."
    )
    if user_exists:
        greeting_text = (
            f"С возвращением, {message.from_user.full_name}!\n"
            "Кажется, вы ранее не приняли условия Политики обработки персональных данных. "
            "Для продолжения, пожалуйста, ознакомьтесь и примите их."
        )
    await message.answer(greeting_text, reply_markup=get_agreement_keyboard())
    await state.set_state(UserAgreement.awaiting_agreement)

@user_router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, sheet_service: AsyncSheetServiceWithQueue):
    user_id = message.from_user.id
    logger.info(f"User {user_id} started the bot.")
    await state.clear() # Очищаем предыдущее состояние на всякий случай

    # Проверяем, есть ли пользователь в базе и принял ли он соглашение
    user_data_list = await sheet_service.read_rows_from_cache("Пользователи", filter_criteria={"user_id": user_id})

    if user_data_list:
        user_gsheet_data = user_data_list[0]
        # В модели is_active и agreement_accepted_at могут быть None если что-то пошло не так при записи
        # или если колонки пустые.
        # Для GSheet "TRUE" / "FALSE" строки, а agreement_accepted_at - дата/время или пусто
        agreement_accepted = bool(user_gsheet_data.get("agreement_accepted_at")) and \
                             str(user_gsheet_data.get("is_active", "")).upper() == "TRUE"

        if agreement_accepted:
            logger.info(f"User {user_id} already accepted agreement. Sending main menu.")
            await message.answer(f"С возвращением, {message.from_user.full_name}! 👋", reply_markup=get_main_menu_keyboard())
            # Здесь можно будет установить состояние главного меню, если потребуется
        else:
            logger.info(f"User {user_id} exists but has not accepted/active agreement. Prompting again.")
            await send_agreement_prompt(message, state, user_exists=True)
    else:
        logger.info(f"New user {user_id}. Prompting for agreement.")
        await send_agreement_prompt(message, state)


@user_router.callback_query(UserAgreementCallback.filter(F.action == "view"), UserAgreement.awaiting_agreement)
async def handle_view_agreement_callback(query: CallbackQuery, state: FSMContext):
    try:
        with open(USER_AGREEMENT_PATH, "r", encoding="utf-8") as f:
            agreement_text = f.read()
        # Ограничение Telegram на длину сообщения ~4096 символов.
        # Если текст очень длинный, его нужно будет разбить или отправить файлом.
        # Пока предполагаем, что он умещается.
        if len(agreement_text) > 4000: # Небольшой запас
             agreement_text = agreement_text[:4000] + "\n...(полный текст слишком длинный для одного сообщения)..."

        await query.message.edit_text(agreement_text, reply_markup=get_view_agreement_keyboard())
        await query.answer()
    except FileNotFoundError:
        logger.error(f"User agreement file not found at {USER_AGREEMENT_PATH}")
        await query.answer("Не удалось загрузить текст соглашения. Пожалуйста, попробуйте позже.", show_alert=True)
    except Exception as e:
        logger.error(f"Error reading user agreement: {e}")
        await query.answer("Произошла ошибка при загрузке соглашения.", show_alert=True)


@user_router.callback_query(UserAgreementCallback.filter(F.action == "back_to_options"), UserAgreement.awaiting_agreement)
async def handle_back_to_agreement_options_callback(query: CallbackQuery, state: FSMContext):
    # Это обработчик для кнопки "Назад" из просмотра текста соглашения
    # По сути, просто переотправляем исходное сообщение с выбором
    greeting_text = (
        f"Здравствуйте, {query.from_user.full_name}!\n"
        "Добро пожаловать в наш магазин парфюмерии Robotiaga Perfumes!\n\n"
        "Для продолжения, пожалуйста, ознакомьтесь с нашей Политикой обработки персональных данных и примите ее условия."
    )
    # Проверяем, есть ли такое сообщение, чтобы отредактировать, иначе новое
    if query.message:
        await query.message.edit_text(greeting_text, reply_markup=get_agreement_keyboard())
    else:
        await query.bot.send_message(query.from_user.id, greeting_text, reply_markup=get_agreement_keyboard())
    await query.answer()


@user_router.callback_query(UserAgreementCallback.filter(F.action == "accept"), UserAgreement.awaiting_agreement)
async def handle_accept_agreement_callback(query: CallbackQuery, state: FSMContext, sheet_service: AsyncSheetServiceWithQueue):
    user = query.from_user
    logger.info(f"User {user.id} accepted the agreement.")

    user_data_payload = {
        "user_id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "agreement_accepted_at": datetime.datetime.now().isoformat(), # Сохраняем в ISO для совместимости с разными форматами дат
        "is_active": "TRUE" # Используем строку "TRUE" как в вашей GSheet модели
    }

    # Пытаемся найти пользователя, чтобы обновить, или создаем нового
    existing_user_list = await sheet_service.read_rows_from_cache("Пользователи", filter_criteria={"user_id": user.id})

    if existing_user_list:
        # Обновляем существующего пользователя
        update_result = await sheet_service.update_rows(
            sheet_alias="Пользователи",
            filter_criteria={"user_id": user.id},
            new_data_payload=user_data_payload
        )
        if update_result > 0:
            logger.info(f"User {user.id} data updated in GSheet.")
        else:
            logger.error(f"Failed to update user {user.id} data in GSheet. Queue ID or error logged in sheet_service.")
            # Можно отправить сообщение об ошибке, но пока просто продолжаем
    else:
        # Создаем нового пользователя
        created_user = await sheet_service.create_row("Пользователи", user_data_payload)
        if created_user:
            logger.info(f"New user {user.id} data created in GSheet.")
        else:
            logger.error(f"Failed to create user {user.id} data in GSheet. Queue ID or error logged in sheet_service.")
            # Можно отправить сообщение об ошибке

    await query.answer("Спасибо! Вы приняли условия.", show_alert=False)
    if query.message: # Удаляем инлайн клавиатуру соглашения
        await query.message.delete_reply_markup()
        await query.message.answer("Отлично! Теперь вы можете пользоваться всеми функциями бота.", reply_markup=get_main_menu_keyboard())
    else: # Если вдруг query.message нет (маловероятно для callback)
        await query.bot.send_message(user.id, "Отлично! Теперь вы можете пользоваться всеми функциями бота.", reply_markup=get_main_menu_keyboard())

    await state.clear() # Сбрасываем состояние


# Обработчик для текстовых сообщений, если пользователь не в каком-то конкретном состоянии
# и пытается что-то написать вместо нажатия кнопок главного меню.
@user_router.message(F.text, lambda msg: msg.text not in ["🛍️ Каталог", "🛒 Корзина", "📦 Мои заказы", "ℹ️ Информация о магазине", "❓ Помощь"])
async def handle_unknown_text_commands_main_menu(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None: # Только если мы в "главном меню" (нет состояния)
        await message.reply("Пожалуйста, используйте кнопки меню для навигации. 👇", reply_markup=get_main_menu_keyboard())