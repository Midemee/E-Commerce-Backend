from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel
from sqlmodel import SQLModel, Field as SQLField, Relationship

from app.models.product import Product


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class CreateOrderItem(BaseModel):
    product_id: UUID
    quantity: int


class CreateOrder(BaseModel):
    customer_id: UUID
    cart_id : UUID


class Order(SQLModel, table=True):
    __tablename__ = "orders"
    id: UUID = SQLField(default_factory=uuid4, primary_key=True)
    customer_id: UUID = SQLField(foreign_key="users.id")
    order_date: datetime = SQLField(default_factory=lambda: datetime.now(timezone.utc))
    total_amount: float
    status: OrderStatus = SQLField(default=OrderStatus.PENDING)

    items: List["OrderItem"] = Relationship(back_populates="order")


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_items"

    id: UUID = SQLField(default_factory=uuid4, primary_key=True)
    order_id: UUID = SQLField(foreign_key="orders.id")
    product_id: UUID = SQLField(foreign_key="products.id")
    quantity: int
    price_purchased: float
    order: Order = Relationship(back_populates="items")

    @property
    def subtotal(self) -> float:
        return self.quantity * self.price_purchased

class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    quantity: int
    price_purchased: float
    subtotal: float
    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: UUID
    customer_id: UUID
    order_date: datetime
    total_amount: float
    status: OrderStatus
    items: List[OrderItemResponse] = []
    model_config = {"from_attributes": True}