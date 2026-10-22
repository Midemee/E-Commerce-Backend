from uuid import uuid4

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlmodel import SQLModel, Session

from app.models.product import Product
from app.models.cart import Cart, CartItem
from app.models.user import User
from app.repositories.cart_repository import CartRepository


class TestCartRepository:
    @pytest.fixture
    def db_session(self):
        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(test_engine)

        with Session(test_engine) as session:
            yield session

        SQLModel.metadata.drop_all(test_engine)


    def create_test_product(self, db_session: Session):
        product = Product(
            name="test_name",
            description="test_description",
            price=5.99,
            quantity=3
        )

        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    def create_test_cart(self, db_session: Session, customer_id=None):
        import uuid
        cart = Cart(
            customer_id=customer_id or uuid.uuid4()
        )
        db_session.add(cart)
        db_session.commit()
        db_session.refresh(cart)
        return cart

    def test_cart_model_functions_poperly(self, db_session):
        test_product = self.create_test_product(db_session)
        test_cart = self.create_test_cart(db_session)

        cart_item = CartItem(
            cart_id=test_cart.id,
            product_id=test_product.id,
            quantity=1,
            product_price=test_product.price
        )

        db_session.add(cart_item)
        db_session.commit()
        db_session.refresh(cart_item)

        saved_item = db_session.get(CartItem, cart_item.id)

        assert saved_item is not None
        assert saved_item.cart_id == test_cart.id
        assert saved_item.product_id == test_product.id
        assert saved_item.quantity == 1

    def test_cart_total_price(self, db_session):
        test_product = self.create_test_product(db_session)
        test_cart = self.create_test_cart(db_session)

        cart_item = CartItem(
            cart_id=test_cart.id,
            product_id=test_product.id,
            quantity=2,
            product_price=test_product.price
        )

        db_session.add(cart_item)
        db_session.commit()

        db_session.refresh(test_cart)

        assert test_cart.total_price == 11.98

    def test_get_or_create_for_customer_creates_a_cart_with_id(self, db_session):
        repository = CartRepository(db_session)
        customer_id = uuid4()

        cart = repository.get_or_create_for_customer(customer_id)

        assert cart.id is not None
        assert cart.customer_id == customer_id

    def test_get_or_create_for_customer_returns_existing_cart(self, db_session):
        repository = CartRepository(db_session)
        customer_id = uuid4()

        first = repository.get_or_create_for_customer(customer_id)
        second = repository.get_or_create_for_customer(customer_id)

        assert first.id == second.id