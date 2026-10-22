from uuid import uuid4

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlmodel import SQLModel, Session, select

from app.repositories.order_repository import OrderRepository
from app.models.order import Order, OrderItem, OrderStatus
from app.enums.user_role import UserRole
from app.models.user import User
from app.models.product import Product
from app.models.cart import Cart, CartItem


class TestOrderRepositoryAdd:

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

    def create_test_customer(self, db_session: Session) -> User:
        customer = User(name="Ada", email="ada@example.com", password="fake-hash", role=UserRole.CUSTOMER)
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)
        return customer

    def create_test_product(self, db_session: Session) -> Product:
        product = Product(name="Widget", description="A test widget", price=10.0, quantity=5)
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    def test_add_returns_the_order_with_an_id(self, db_session: Session):
        repo = OrderRepository(db_session)
        customer = self.create_test_customer(db_session)
        product = self.create_test_product(db_session)

        order = Order(customer_id=customer.id, total_amount=20.0, status=OrderStatus.PENDING)
        items = [OrderItem(product_id=product.id, quantity=2, price_purchased=10.0)]

        result = repo.add(order, items)

        assert result.id is not None
        assert result.total_amount == 20.0
        assert result.status == OrderStatus.PENDING

    def test_add_actually_persists_the_order_in_the_database(self, db_session: Session):
        repo = OrderRepository(db_session)
        customer = self.create_test_customer(db_session)
        product = self.create_test_product(db_session)

        order = Order(customer_id=customer.id, total_amount=15.0)
        items = [OrderItem(product_id=product.id, quantity=1, price_purchased=15.0)]

        saved = repo.add(order, items)

        # Query MySQL/SQLite directly, bypassing the repository entirely,
        # to prove the row is really there and not just held in memory.
        row_in_db = db_session.get(Order, saved.id)
        assert row_in_db is not None
        assert row_in_db.customer_id == customer.id

    def test_add_saves_every_item_in_the_list(self, db_session: Session):
        repo = OrderRepository(db_session)
        customer = self.create_test_customer(db_session)
        product = self.create_test_product(db_session)

        order = Order(customer_id=customer.id, total_amount=30.0)
        items = [
            OrderItem(product_id=product.id, quantity=1, price_purchased=10.0),
            OrderItem(product_id=product.id, quantity=2, price_purchased=10.0),
        ]

        saved_order = repo.add(order, items)

        statement = select(OrderItem).where(OrderItem.order_id == saved_order.id)
        saved_items = db_session.exec(statement).all()

        assert len(saved_items) == 2

    def test_add_links_every_item_to_the_correct_order_id(self, db_session: Session):
        repo = OrderRepository(db_session)
        customer = self.create_test_customer(db_session)
        product = self.create_test_product(db_session)

        order = Order(customer_id=customer.id, total_amount=10.0)
        items = [OrderItem(product_id=product.id, quantity=1, price_purchased=10.0)]

        saved_order = repo.add(order, items)

        # Before add() ran, this item had NO order_id at all.
        # This confirms add() is the thing that actually set it.
        assert items[0].order_id == saved_order.id

    def test_add_preserves_each_items_price_and_quantity(self, db_session: Session):
        repo = OrderRepository(db_session)
        customer = self.create_test_customer(db_session)
        product = self.create_test_product(db_session)

        order = Order(customer_id=customer.id, total_amount=25.0)
        items = [OrderItem(product_id=product.id, quantity=2, price_purchased=12.5)]

        saved_order = repo.add(order, items)

        statement = select(OrderItem).where(OrderItem.order_id == saved_order.id)
        saved_item = db_session.exec(statement).first()

        assert saved_item.quantity == 2
        assert saved_item.price_purchased == 12.5

    def test_get_returns_none_when_order_does_not_exist(self, db_session: Session):
        repo = OrderRepository(db_session)

        result = repo.get(uuid4())

        assert result is None

    def test_add_with_an_empty_items_list_still_saves_the_order(self, db_session: Session):
        repo = OrderRepository(db_session)
        customer = self.create_test_customer(db_session)

        order = Order(customer_id=customer.id, total_amount=0.0)

        saved_order = repo.add(order, [])

        assert saved_order.id is not None
        statement = select(OrderItem).where(OrderItem.order_id == saved_order.id)
        assert db_session.exec(statement).all() == []