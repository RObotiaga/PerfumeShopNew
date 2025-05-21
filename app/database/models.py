# robotiaga-perfumeshopnew/app/database/models.py
from sqlalchemy import (
    Integer,
    String,
    Float,
    DateTime,
    Date,
    Text,
    Boolean,
)  # Добавлен Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import datetime
from typing import Optional


# Base for Google Sheet ORM models
class GSheetBase(DeclarativeBase):
    pass


# Base for SQLite ORM models
class SqliteBase(DeclarativeBase):
    pass


# --- Google Sheet ORM Model Definitions ---


class User(GSheetBase):  # НОВАЯ МОДЕЛЬ
    __tablename__ = "Пользователи"
    user_id: Mapped[int] = mapped_column(
        "ID Пользователя", Integer, primary_key=True, autoincrement=False
    )
    username: Mapped[Optional[str]] = mapped_column("Username", String, nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(
        "Имя", String, nullable=True
    )  # В ТГ может не быть
    last_name: Mapped[Optional[str]] = mapped_column(
        "Фамилия", String, nullable=True
    )  # В ТГ может не быть
    agreement_accepted_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        "Принял ПС", DateTime, nullable=True
    )
    is_active: Mapped[Optional[str]] = mapped_column(
        "Активен", String, nullable=True
    )  # Используем String ("TRUE"/"FALSE") для совместимости с GSheet

    def __repr__(self):
        return f"<User(user_id='{self.user_id}', username='{self.username}')>"


class Product(GSheetBase):
    __tablename__ = "Товары"
    product_id: Mapped[int] = mapped_column(
        "ID Товара", Integer, primary_key=True, autoincrement=False
    )
    product_name: Mapped[Optional[str]] = mapped_column(
        "Название Товара", String, nullable=True
    )
    photo_url: Mapped[Optional[str]] = mapped_column(
        "Ссылка на фото", String, nullable=True
    )
    category: Mapped[Optional[str]] = mapped_column("Категория", String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column("Описание", Text, nullable=True)
    price_per_unit: Mapped[Optional[float]] = mapped_column(
        "Цена за единицу", Float, nullable=True
    )
    unit_of_measure: Mapped[Optional[str]] = mapped_column(
        "Единица измерения", String, nullable=True
    )  # мл, шт
    product_type: Mapped[Optional[str]] = mapped_column(
        "Тип товара", String, nullable=True
    )  # Объемный, Штучный
    portion_type: Mapped[Optional[str]] = mapped_column(
        "Тип распива", String, nullable=True
    )  # Обычный, Совместный
    order_step: Mapped[Optional[str]] = mapped_column(
        "Шаг заказа", String, nullable=True
    )  # ИЗМЕНЕНО на String, например "2.5;5;7.5" или "1" для штучных
    available_quantity: Mapped[Optional[float]] = mapped_column(
        "Доступное количество", Float, nullable=True
    )
    status: Mapped[Optional[str]] = mapped_column(
        "Статус", String, nullable=True
    )  # Например, "В наличии", "Нет в наличии", "Забронирован"

    def __repr__(self):
        return f"<Product(product_id='{self.product_id}', product_name='{self.product_name}')>"


class Order(GSheetBase):
    __tablename__ = "Заказы"
    order_number: Mapped[str] = mapped_column("Номер заказа", String, primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column("ID пользователя", String, nullable=True) # ID пользователя Telegram
    order_date: Mapped[Optional[datetime.date]] = mapped_column("дата", Date, nullable=True) # Дата создания заказа
    item_list_raw: Mapped[Optional[str]] = mapped_column("Список товаров(ID:Тип:Количество)", String, nullable=True)
    total_amount: Mapped[Optional[float]] = mapped_column("Общая сумма", Float, nullable=True) # Сумма товаров БЕЗ доставки
    delivery_cost: Mapped[Optional[float]] = mapped_column("Стоимость доставки", Float, nullable=True) # Стоимость доставки

    delivery_type_name: Mapped[Optional[str]] = mapped_column("Тип доставки", String, nullable=True) # Название типа доставки (из таблицы "Тип доставки")
    delivery_address: Mapped[Optional[str]] = mapped_column("Адрес доставки", Text, nullable=True) # Для курьерской/почтовой доставки
    comment: Mapped[Optional[str]] = mapped_column("Комментарий к заказу", Text, nullable=True) # Комментарий клиента
    status: Mapped[Optional[str]] = mapped_column("Статус", String, nullable=True) # Статус из ТЗ: "Принят", "В обработке", "Отправлен", и т.д.

    # УБРАНЫ поля: contact_phone, contact_name, payment_type, payment_status, final_amount

    def __repr__(self):
        return f"<Order(order_number='{self.order_number}', user_id='{self.user_id}')>"

class DeliveryType(GSheetBase):
    __tablename__ = "Тип доставки"  # Название листа из ТЗ - "Настройки доставки"
    delivery_type_name: Mapped[str] = mapped_column(
        "Тип доставки", String, primary_key=True
    )
    cost: Mapped[Optional[float]] = mapped_column("Стоимость", Float, nullable=True)
    is_active: Mapped[Optional[str]] = mapped_column(
        "Активность", String, nullable=True
    )  # TRUE/FALSE

    def __repr__(self):
        return f"<DeliveryType(delivery_type_name='{self.delivery_type_name}', is_active='{self.is_active}')>"


class PaymentSetting(GSheetBase):
    __tablename__ = "Настройка платежей"
    payment_format: Mapped[str] = mapped_column(
        "Формат оплаты", String, primary_key=True
    )  # "СБП", "Tinkoff"
    recipient_name: Mapped[Optional[str]] = mapped_column(
        "Наименование получателя", String, nullable=True
    )
    account_number: Mapped[Optional[str]] = mapped_column(
        "Номер счета", String, nullable=True
    )
    bank_name: Mapped[Optional[str]] = mapped_column("Банк", String, nullable=True)
    bic: Mapped[Optional[str]] = mapped_column("БИК", String, nullable=True)
    inn: Mapped[Optional[str]] = mapped_column("ИНН", String, nullable=True)
    terminal_key: Mapped[Optional[str]] = mapped_column(
        "TerminalKey", String, nullable=True
    )
    password: Mapped[Optional[str]] = mapped_column(
        "Password", String, nullable=True
    )  # Для Tinkoff API

    def __repr__(self):
        return f"<PaymentSetting(payment_format='{self.payment_format}')>"


class Mailing(GSheetBase):
    __tablename__ = "Рассылки"
    mailing_id: Mapped[int] = mapped_column(
        "ID рассылки", Integer, primary_key=True, autoincrement=False
    )
    message_text: Mapped[Optional[str]] = mapped_column(
        "Текст сообщения", Text, nullable=True
    )
    send_time_str: Mapped[Optional[str]] = mapped_column(
        "Время отправки (дата/время)", String, nullable=True
    )
    is_sent: Mapped[Optional[str]] = mapped_column(
        "Отправлено", String, nullable=True
    )  # ДА/НЕТ

    def __repr__(self):
        return f"<Mailing(mailing_id='{self.mailing_id}', is_sent='{self.is_sent}')>"


# --- SQLite ORM Model for Pending Operations ---
class PendingSheetOperation(SqliteBase):
    __tablename__ = (
        "pending_sheet_operations"  # Это PENDING_OPERATIONS_TABLE_NAME из config.py
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sheet_alias: Mapped[str] = mapped_column(String, nullable=False)
    operation_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # CREATE, UPDATE, DELETE
    filter_criteria_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String, default="pending", nullable=False
    )  # pending, processing, retry, failed_max_attempts, failed_worker_error
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return (
            f"<PendingSheetOperation(id={self.id}, sheet='{self.sheet_alias}', op='{self.operation_type}', "
            f"status='{self.status}', attempts={self.attempts})>"
        )
