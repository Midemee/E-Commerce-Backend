from datetime import datetime, timezone
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField, Relationship, SQLModel



class CreateCart(BaseModel):
    product_id: UUID
    quantity: int = Field(..., gt=0)


class CartItem(SQLModel, table=True):
    __tablename__ = "cart_items"
    id: UUID = SQLField(default_factory=uuid4, primary_key=True)
    cart_id: UUID = SQLField(foreign_key="carts.id")
    product_id: UUID = SQLField(foreign_key="products.id")
    quantity: int = SQLField(gt=0)
    product_price: float = SQLField(gt=0)
    cart: "Cart" = Relationship(back_populates="items")
    product: "Product" = Relationship(back_populates="cart_items")



class Cart(SQLModel, table=True):
    __tablename__ = "carts"

    id: UUID = SQLField(default_factory=uuid4, primary_key=True)
    customer_id: UUID = SQLField(foreign_key="users.id")
    items: list["CartItem"] = Relationship(back_populates="cart")
    created_at: datetime = SQLField(default_factory=lambda: datetime.now(timezone.utc))


    @property
    def total_price(self) -> float:
        total = 0.0

        for  item in self.items:
            if item.product:
                total += item.product_price * item.quantity

        return total