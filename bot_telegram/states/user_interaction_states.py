# bot_telegram/states/user_interaction_states.py
from aiogram.fsm.state import State, StatesGroup

class UserAgreement(StatesGroup):
    awaiting_agreement = State() # Состояние ожидания реакции на пользовательское соглашение

class CatalogNavigation(StatesGroup):
    choosing_category = State()
    viewing_products = State() # page_number, category_name
    viewing_product_detail = State() # product_id, source_page, source_category

class CartInteraction(StatesGroup):
    viewing_cart = State()
    # Можно добавить состояния для оформления заказа, если потребуется пошаговый ввод данных
    # checkout_entering_name = State()
    # checkout_entering_phone = State()
    # checkout_entering_address = State()

# Другие группы состояний по мере необходимости (например, для оформления заказа, обратной связи)