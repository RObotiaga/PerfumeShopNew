# robotiaga-perfumeshopnew/app/database/models.py
from sqlalchemy import Integer, String, Float, DateTime, Date, Text # Обновлен список импортов sqlalchemy типов
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column # Обновлен импорт для SQLAlchemy 2.0+
import datetime
from typing import Optional # Убраны неиспользуемые List, Dict, Any, Type

# Base for Google Sheet ORM models
class GSheetBase(DeclarativeBase):
    pass

# Base for SQLite ORM models
class SqliteBase(DeclarativeBase):
    pass


# --- Google Sheet ORM Model Definitions (обновленный синтаксис) ---
class Product(GSheetBase):
    __tablename__ = "Товары"
    # Имя колонки в Google Sheets указывается первым аргументом в mapped_column, если оно отличается от имени атрибута.
    product_id: Mapped[int] = mapped_column("ID Товара", Integer, primary_key=True, autoincrement=False)
    product_name: Mapped[Optional[str]] = mapped_column("Название Товара", String, nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column("Ссылка на фото", String, nullable=True)
    category: Mapped[Optional[str]] = mapped_column("Категория", String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column("Описание", Text, nullable=True)
    price_per_unit: Mapped[Optional[float]] = mapped_column("Цена за единицу", Float, nullable=True)
    unit_of_measure: Mapped[Optional[str]] = mapped_column("Единица измерения", String, nullable=True)
    product_type: Mapped[Optional[str]] = mapped_column("Тип товара", String, nullable=True)
    portion_type: Mapped[Optional[str]] = mapped_column("Тип распива", String, nullable=True)
    order_step: Mapped[Optional[float]] = mapped_column("Шаг заказа", Float, nullable=True)
    available_quantity: Mapped[Optional[float]] = mapped_column("Доступное количество", Float, nullable=True)
    status: Mapped[Optional[str]] = mapped_column("Статус", String, nullable=True)

    def __repr__(self):
        return f"<Product(product_id='{self.product_id}', product_name='{self.product_name}')>"


class Order(GSheetBase):
    __tablename__ = "Заказы"
    order_number: Mapped[str] = mapped_column("Номер заказа", String, primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column("ID пользователя", String, nullable=True)
    order_date: Mapped[Optional[datetime.date]] = mapped_column("дата", Date, nullable=True)
    # Атрибут item_list_raw сопоставляется с колонкой "Список товаров(ID:Тип:Количество)"
    item_list_raw: Mapped[Optional[str]] = mapped_column("Список товаров(ID:Тип:Количество)", String, nullable=True)
    total_amount: Mapped[Optional[float]] = mapped_column("Общая сумма", Float, nullable=True)
    status: Mapped[Optional[str]] = mapped_column("Статус", String, nullable=True)

    def __repr__(self):
        return f"<Order(order_number='{self.order_number}', user_id='{self.user_id}')>"


class DeliveryType(GSheetBase):
    __tablename__ = "Тип доставки"
    delivery_type_name: Mapped[str] = mapped_column("Тип доставки", String, primary_key=True)
    cost: Mapped[Optional[float]] = mapped_column("Стоимость", Float, nullable=True)
    # Поле is_active остается строкой, как в оригинале. Если это булево значение, можно рассмотреть sqlalchemy.Boolean
    is_active: Mapped[Optional[str]] = mapped_column("Активность", String, nullable=True)

    def __repr__(self):
        return f"<DeliveryType(delivery_type_name='{self.delivery_type_name}', is_active='{self.is_active}')>"


class PaymentSetting(GSheetBase):
    __tablename__ = "Настройка платежей"
    payment_format: Mapped[str] = mapped_column("Формат оплаты", String, primary_key=True)
    recipient_name: Mapped[Optional[str]] = mapped_column("Наименование получателя", String, nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column("Номер счета", String, nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column("Банк", String, nullable=True)
    bic: Mapped[Optional[str]] = mapped_column("БИК", String, nullable=True)
    inn: Mapped[Optional[str]] = mapped_column("ИНН", String, nullable=True)
    terminal_key: Mapped[Optional[str]] = mapped_column("TerminalKey", String, nullable=True)
    password: Mapped[Optional[str]] = mapped_column("Password", String, nullable=True)

    def __repr__(self):
        return f"<PaymentSetting(payment_format='{self.payment_format}')>"


class Mailing(GSheetBase):
    __tablename__ = "Рассылки"
    mailing_id: Mapped[int] = mapped_column("ID рассылки", Integer, primary_key=True, autoincrement=False)
    message_text: Mapped[Optional[str]] = mapped_column("Текст сообщения", Text, nullable=True)
    send_time_str: Mapped[Optional[str]] = mapped_column("Время отправки (дата/время)", String, nullable=True)
    # Поле is_sent остается строкой.
    is_sent: Mapped[Optional[str]] = mapped_column("Отправлено", String, nullable=True)

    def __repr__(self):
        return f"<Mailing(mailing_id='{self.mailing_id}', is_sent='{self.is_sent}')>"


# --- SQLite ORM Model for Pending Operations (обновленный синтаксис и тип для JSON-строк) ---
class PendingSheetOperation(SqliteBase):
    __tablename__ = "pending_sheet_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sheet_alias: Mapped[str] = mapped_column(String, nullable=False)
    operation_type: Mapped[str] = mapped_column(String, nullable=False)

    # Храним JSON как строку (Text), так как используется явный json.dumps
    filter_criteria_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Поля с default значениями обычно не nullable
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return (
            f"<PendingSheetOperation(id={self.id}, sheet='{self.sheet_alias}', op='{self.operation_type}', "
            f"status='{self.status}', attempts={self.attempts})>"
        )