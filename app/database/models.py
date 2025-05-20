from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Boolean, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Product(Base):
    __tablename__ = "Товары"

    product_id = Column("ID Товара", Integer, primary_key=True, autoincrement=False)
    product_name = Column("Название Товара", String)
    photo_url = Column("Ссылка на фото", String)
    category = Column("Категория", String)
    description = Column("Описание", Text)
    price_per_unit = Column("Цена за единицу", Float)
    unit_of_measure = Column("Единица измерения", String)
    product_type = Column("Тип товара", String)
    portion_type = Column("Тип распива", String)
    order_step = Column("Шаг заказа", Float)
    available_quantity = Column("Доступное количество", Float)
    status = Column("Статус", String)

    def __repr__(self):
        return f"<Product(product_id='{self.product_id}', product_name='{self.product_name}')>"


class Order(Base):
    __tablename__ = "Заказы"
    order_number = Column("Номер заказа", String, primary_key=True)
    user_id = Column("ID пользователя", String)
    order_date = Column("дата", Date)
    item_list_raw = Column(
        "Список товаров(ID:Тип:Количество)", String, key="item_list_raw"
    )
    total_amount = Column("Общая сумма", Float)
    status = Column("Статус", String)

    def __repr__(self):
        return f"<Order(order_number='{self.order_number}', user_id='{self.user_id}')>"


class DeliveryType(Base):
    __tablename__ = "Тип доставки"
    delivery_type_name = Column(
        "Тип доставки", String, primary_key=True, key="delivery_type_name"
    )
    cost = Column("Стоимость", Float)
    is_active = Column("Активность", String, key="is_active")

    def __repr__(self):
        return f"<DeliveryType(delivery_type_name='{self.delivery_type_name}', is_active='{self.is_active}')>"


class PaymentSetting(Base):
    __tablename__ = "Настройка платежей"
    payment_format = Column("Формат оплаты", String, primary_key=True)
    recipient_name = Column("Наименование получателя", String)
    account_number = Column("Номер счета", String)
    bank_name = Column("Банк", String)
    bic = Column("БИК", String)
    inn = Column("ИНН", String)
    terminal_key = Column("TerminalKey", String)
    password = Column("Password", String)

    def __repr__(self):
        return f"<PaymentSetting(payment_format='{self.payment_format}')>"


class Mailing(Base):
    __tablename__ = "Рассылки"
    mailing_id = Column("ID рассылки", Integer, primary_key=True, autoincrement=False)
    message_text = Column("Текст сообщения", Text)
    send_time_str = Column("Время отправки (дата/время)", String, key="send_time_str")
    is_sent = Column("Отправлено", String, key="is_sent")

    def __repr__(self):
        return f"<Mailing(mailing_id='{self.mailing_id}', is_sent='{self.is_sent}')>"
