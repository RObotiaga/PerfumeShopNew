# robotiaga-perfumeshopnew/app/database/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, Mapped, mapped_column  # Для новых версий SQLAlchemy
import datetime
from typing import Dict, List, Any, Optional, Type

# Base for Google Sheet ORM models (could be the same as for SQLite if no conflicts)
GSheetBase = declarative_base()  # Используем отдельный Base для моделей Google Sheets, на всякий случай

# Base for SQLite ORM models
SqliteBase = declarative_base()


# --- Google Sheet ORM Model Definitions (как и были) ---
class Product(GSheetBase):
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


class Order(GSheetBase):
    __tablename__ = "Заказы"
    order_number = Column("Номер заказа", String, primary_key=True)
    user_id = Column("ID пользователя", String)
    order_date = Column("дата", Date)
    item_list_raw = Column("Список товаров(ID:Тип:Количество)", String, key="item_list_raw")
    total_amount = Column("Общая сумма", Float)
    status = Column("Статус", String)

    def __repr__(self):
        return f"<Order(order_number='{self.order_number}', user_id='{self.user_id}')>"


class DeliveryType(GSheetBase):
    __tablename__ = "Тип доставки"
    delivery_type_name = Column("Тип доставки", String, primary_key=True, key="delivery_type_name")
    cost = Column("Стоимость", Float)
    is_active = Column("Активность", String, key="is_active")

    def __repr__(self):
        return f"<DeliveryType(delivery_type_name='{self.delivery_type_name}', is_active='{self.is_active}')>"


class PaymentSetting(GSheetBase):
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


class Mailing(GSheetBase):
    __tablename__ = "Рассылки"
    mailing_id = Column("ID рассылки", Integer, primary_key=True, autoincrement=False)
    message_text = Column("Текст сообщения", Text)
    send_time_str = Column("Время отправки (дата/время)", String, key="send_time_str")
    is_sent = Column("Отправлено", String, key="is_sent")

    def __repr__(self):
        return f"<Mailing(mailing_id='{self.mailing_id}', is_sent='{self.is_sent}')>"


# --- SQLite ORM Model for Pending Operations ---
class PendingSheetOperation(SqliteBase):
    __tablename__ = "pending_sheet_operations"  # Имя таблицы из config.py

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sheet_alias: Mapped[str] = mapped_column(String, nullable=False)
    operation_type: Mapped[str] = mapped_column(String, nullable=False)  # "CREATE", "UPDATE", "DELETE"

    # Для UPDATE и DELETE, filter_criteria содержит условия поиска
    # Для CREATE, это поле может быть NULL или содержать PK для справки
    filter_criteria_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Храним JSON как строку

    # Для CREATE и UPDATE, data_payload содержит данные для записи/обновления
    # Для DELETE, это поле может быть NULL
    data_payload_json: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Храним JSON как строку

    status: Mapped[str] = mapped_column(String, default="pending")  # "pending", "processing", "success", "failed"
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return (
            f"<PendingSheetOperation(id={self.id}, sheet='{self.sheet_alias}', op='{self.operation_type}', "
            f"status='{self.status}', attempts={self.attempts})>"
        )