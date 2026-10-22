from uuid import uuid4

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlmodel import SQLModel, Session

from app.models.product import AddProduct, Product
from app.repositories.product_repository import ProductRepository


from app.models.product import Product
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem, OrderStatus
from app.models.user import User

class TestProductRepository:
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


    def create_test_product(self):
        product_id = uuid4()
        product = Product(
            id =product_id,
            name = "test_name",
            description = "test_description",
            price = 5.99,
            quantity = 3
        )

        return product

    def test_that_save_product_saved_product_id_is_created(self, db_session : Session):

        repo = ProductRepository(session = db_session)

        product = self.create_test_product()

        saved_product = repo.save(product)

        assert saved_product.id is not None


    def test_that_save_product_saved_product_find_by_id_returns_product(self, db_session : Session):

        repo = ProductRepository(session = db_session)

        product = self.create_test_product()

        saved_product = repo.save(product)

        assert saved_product.id is not None


        print(f"Gotcha! >> {saved_product.id}")
        assert repo.find_by_id(saved_product.id) == saved_product