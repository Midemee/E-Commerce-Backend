
import uuid
from uuid import UUID

from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField, Relationship


class AddProduct(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    description: str = Field(min_length=3, max_length=100)
    price: float = Field(gt=0)
    quantity: int = Field(gt=0)
    image_url: str | None = None


class UpdateProduct(BaseModel):
    id: UUID
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=3, max_length=100)
    price: float = Field(gt=0)
    quantity: int = Field(gt=0)
    image_url: str | None = None


class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: uuid.UUID = SQLField(
        default_factory=uuid.uuid4,
        primary_key=True
    )
    name: str = Field(min_length=3, max_length=100)
    description: str = Field(default=None, min_length=3, max_length=100)
    price: float
    quantity: int
    image_url: str | None = SQLField(default=None)

    cart_items: list["CartItem"] = Relationship(
        back_populates="product"
    )
