# bot_telegram/modules/user_management/handlers.py
import logging
import datetime

from aiogram import Router, F, types
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery  # CallbackQuery уже был, но теперь используется активнее

from app.database import AsyncSheetServiceWithQueue, User
from bot_telegram.states.user_interaction_states import UserAgreement, CatalogNavigation  # ДОБАВЛЕН CatalogNavigation
from .keyboards import get_agreement_keyboard, get_main_menu_keyboard
from bot_telegram.utils.callback_data_factory import UserAgreementCallback, \
    NavigationCallback  # ДОБАВЛЕН NavigationCallback

logger = logging.getLogger(__name__)
user_router = Router()


# Функция для отправки или редактирования главного меню
async def send_or_edit_main_menu(message_or_query: Message | CallbackQuery, state: FSMContext, text: str | None = None):
    user_full_name = message_or_query.from_user.full_name
    if text is None:
        text = f"{user_full_name}, добро пожаловать в главное меню!"

    # Убираем предыдущее состояние, если мы перешли в главное меню
    # кроме случая, когда мы уже в главном меню и просто нажимаем кнопку "В главное меню"
    # current_state = await state.get_state()
    # if current_state is not None: # Это вызовет проблемы, если главное меню - это тоже состояние
    await state.clear()  # Пока очищаем состояние при любом входе в главное меню

    if isinstance(message_or_query, Message):
        await message_or_query.answer(text, reply_markup=get_main_menu_keyboard())
    elif isinstance(message_or_query, CallbackQuery):
        if message_or_query.message:
            try:
                await message_or_query.message.edit_text(text, reply_markup=get_main_menu_keyboard())
            except Exception:  # Если сообщение не изменилось или другая ошибка редактирования
                await message_or_query.message.answer(text, reply_markup=get_main_menu_keyboard())
                await message_or_query.message.delete()  # Удаляем старое сообщение с инлайн кнопками, если не смогли отредактировать
            await message_or_query.answer()


async def send_agreement_prompt(message: Message, state: FSMContext, user_exists: bool = False):
    greeting_text = (
        f"Здравствуйте, {message.from_user.full_name}!\n"
        "Добро пожаловать в наш магазин парфюмерии Robotiaga Perfumes!\n\n"
        "Для продолжения, пожалуйста, ознакомьтесь с нашей Политикой обработки персональных данных (ссылка ниже) и примите ее условия."
    )
    if user_exists:
        greeting_text = (
            f"С возвращением, {message.from_user.full_name}!\n"
            "Кажется, вы ранее не приняли условия Политики обработки персональных данных. "
            "Для продолжения, пожалуйста, ознакомьтесь (ссылка ниже) и примите их."
        )
    await message.answer(greeting_text, reply_markup=get_agreement_keyboard())
    await state.set_state(UserAgreement.awaiting_agreement)


@user_router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, sheet_service: AsyncSheetServiceWithQueue):
    user_id = message.from_user.id
    logger.info(f"User {user_id} ({message.from_user.full_name}) started the bot.")
    await state.clear()

    user_data_list = await sheet_service.read_rows_from_cache("Пользователи", filter_criteria={"user_id": user_id})

    if user_data_list:
        user_gsheet_data = user_data_list[0]
        agreement_accepted = bool(user_gsheet_data.get("agreement_accepted_at")) and \
                             str(user_gsheet_data.get("is_active", "")).upper() == "TRUE"

        if agreement_accepted:
            logger.info(f"User {user_id} already accepted agreement. Sending main menu.")
            # ИЗМЕНЕНО: Отправляем инлайн меню
            await send_or_edit_main_menu(message, state, f"С возвращением, {message.from_user.full_name}! 👋")
        else:
            logger.info(f"User {user_id} exists but has not accepted/active agreement. Prompting again.")
            await send_agreement_prompt(message, state, user_exists=True)
    else:
        logger.info(f"New user {user_id}. Prompting for agreement.")
        await send_agreement_prompt(message, state)


@user_router.callback_query(UserAgreementCallback.filter(F.action == "accept"), UserAgreement.awaiting_agreement)
async def handle_accept_agreement_callback(query: CallbackQuery, state: FSMContext,
                                           sheet_service: AsyncSheetServiceWithQueue):
    user = query.from_user
    logger.info(f"User {user.id} accepted the agreement.")

    user_data_payload = {
        "user_id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "agreement_accepted_at": datetime.datetime.now().isoformat(),
        "is_active": "TRUE"
    }

    existing_user_list = await sheet_service.read_rows_from_cache("Пользователи", filter_criteria={"user_id": user.id})

    if existing_user_list:
        update_result = await sheet_service.update_rows(
            sheet_alias="Пользователи",
            filter_criteria={"user_id": user.id},
            new_data_payload=user_data_payload
        )
        if update_result > 0:
            logger.info(f"User {user.id} data update queued/optimistically updated.")
        else:
            logger.error(f"Failed to queue update for user {user.id} data. See sheet_service logs.")
    else:
        created_user = await sheet_service.create_row("Пользователи", user_data_payload)
        if created_user:
            logger.info(f"New user {user.id} data queued/optimistically created.")
        else:
            logger.error(f"Failed to queue creation for user {user.id} data. See sheet_service logs.")

    await query.answer("Спасибо! Вы приняли условия.", show_alert=False)
    text_after_agreement = "Отлично! Теперь вы можете пользоваться всеми функциями бота."
    if query.message:
        # Удаляем старое сообщение с кнопками соглашения
        await query.message.delete()
        # Отправляем новое сообщение с главным меню
        await query.message.answer(text_after_agreement, reply_markup=get_main_menu_keyboard())
    else:  # Маловероятно для callback
        await query.bot.send_message(user.id, text_after_agreement, reply_markup=get_main_menu_keyboard())

    await state.clear()  # Сбрасываем состояние (UserAgreement.awaiting_agreement)


# --- ОБНОВЛЕННЫЕ/НОВЫЕ ОБРАБОТЧИКИ ДЛЯ КНОПОК ГЛАВНОГО МЕНЮ (Inline) ---

# Обработчик для кнопки "В главное меню" из других разделов
@user_router.callback_query(NavigationCallback.filter(F.to == "main_menu"))
async def handle_nav_to_main_menu(query: CallbackQuery, state: FSMContext):
    logger.info(f"User {query.from_user.id} navigated to main menu.")
    await send_or_edit_main_menu(query, state)
    await query.answer()


# Обработчик для кнопки "Каталог" (переход к хэндлерам каталога)
# Он останется здесь, но основная логика каталога будет в catalog/handlers.py
# Этот обработчик будет импортирован и использован в catalog_router или наоборот,
# catalog_router будет импортирован в user_router.
# Пока что оставим как заглушку, и потом перенесем/дополним.
# @user_router.callback_query(NavigationCallback.filter(F.to == "catalog"), StateFilter(None))
# async def handle_catalog_button_nav(query: CallbackQuery, state: FSMContext, sheet_service: AsyncSheetServiceWithQueue):
#     logger.info(f"User {query.from_user.id} pressed 'Каталог' from main menu.")
#     await state.set_state(CatalogNavigation.choosing_category)
#     # Здесь будет логика отображения категорий из catalog/handlers.py
#     # Например: await show_categories(query, state, sheet_service)
#     # Пока что:
#     if query.message:
#         await query.message.edit_text("Вы выбрали 'Каталог'. Загружаем категории...", reply_markup=None) # Убрать старые кнопки
#     await query.answer("Загрузка категорий...")
# Эта логика будет перенесена в catalog_handlers.py


@user_router.callback_query(NavigationCallback.filter(F.to == "cart"),
                            StateFilter(None))  # StateFilter(None) - если из главного меню (нет состояния)
async def handle_cart_button_nav(query: CallbackQuery, state: FSMContext):
    logger.info(f"User {query.from_user.id} pressed 'Корзина'")
    if query.message:
        await query.message.edit_text("Вы выбрали 'Корзина'. Этот раздел сейчас в разработке.",
                                      reply_markup=get_main_menu_keyboard())  # Для примера оставляем меню
    await query.answer()


@user_router.callback_query(NavigationCallback.filter(F.to == "my_orders"), StateFilter(None))
async def handle_my_orders_button_nav(query: CallbackQuery, state: FSMContext):
    logger.info(f"User {query.from_user.id} pressed 'Мои заказы'")
    if query.message:
        await query.message.edit_text("Вы выбрали 'Мои заказы'. Этот раздел сейчас в разработке.",
                                      reply_markup=get_main_menu_keyboard())
    await query.answer()


@user_router.callback_query(NavigationCallback.filter(F.to == "info"), StateFilter(None))
async def handle_info_button_nav(query: CallbackQuery, state: FSMContext):
    logger.info(f"User {query.from_user.id} pressed 'Информация о магазине'")
    # ТЗ (3.1.1.3): Кнопки отображаются в виде клавиатуры Telegram. Это было для Reply.
    # Теперь это инлайн, текст будет в сообщении.
    info_text = "Robotiaga Perfumes - ваш лучший выбор изысканной парфюмерии.\nКонтакты: @your_admin_contact\nЧасы работы: 10:00 - 20:00"
    if query.message:
        await query.message.edit_text(info_text,
                                      reply_markup=get_main_menu_keyboard())  # Можно добавить кнопку "Назад в меню" или оставить полное меню
    await query.answer()


@user_router.callback_query(NavigationCallback.filter(F.to == "help"), StateFilter(None))
async def handle_help_button_nav(query: CallbackQuery, state: FSMContext):
    logger.info(f"User {query.from_user.id} pressed 'Помощь'")
    # ТЗ (7): "Связаться с менеджером" (переход в чат с Telegram-менеджером).
    # Текст после нажатия: "Здравствуйте! Ваш запрос принят в обработку..."
    help_text = "Здравствуйте! Ваш запрос принят в обработку, мы на связи с 11:00 - 22:00(нск), скоро свяжемся с вами! ❤️\n\nВы также можете написать напрямую нашему менеджеру: @YourAdminUsername"  # Замените на реальный username
    if query.message:
        # Можно добавить кнопку для прямого перехода к менеджеру, если он публичный
        # builder = InlineKeyboardBuilder()
        # builder.button(text="✍️ Написать менеджеру", url="https://t.me/YourAdminUsername")
        # builder.button(text="⬅️ В главное меню", callback_data=NavigationCallback(to="main_menu").pack())
        # await query.message.edit_text(help_text, reply_markup=builder.as_markup())
        await query.message.edit_text(help_text, reply_markup=get_main_menu_keyboard())  # Пока оставим полное меню
    await query.answer()


# Обработчик для текстовых сообщений, если пользователь не в каком-то конкретном состоянии
# и пытается что-то написать. Для инлайн меню этот обработчик менее актуален,
# но может словить случайный текст.
@user_router.message(F.text, StateFilter(None))
async def handle_unknown_text_main_menu(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} sent unknown text '{message.text}' while in main menu (no state).")
    await message.reply(
        "Пожалуйста, используйте кнопки для навигации. 👇",
        reply_markup=get_main_menu_keyboard()  # Отправляем инлайн-меню в ответ
    )