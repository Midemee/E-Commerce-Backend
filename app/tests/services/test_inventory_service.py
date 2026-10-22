from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlmodel import SQLModel, Session, create_engine, StaticPool
from app.models.cart import Cart, CartItem
from app.models.product import Product, AddProduct, UpdateProduct
from app.models.user import User
from app.repositories.product_repository import ProductRepository
from app.services.inventory_service import InventoryService
from app.exception.product_not_found_exception import ProductNotFoundException
from app.exception.product_stock_exception import ProductStockException

class TestInventoryService:
    @pytest.fixture(name="session")
    def session_fixture(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            yield session
        SQLModel.metadata.drop_all(engine)

    @pytest.fixture
    def product_repo(self, session):
        return ProductRepository(session=session)

    @pytest.fixture
    def service(self, product_repo):
        return InventoryService(repository=product_repo)

    @staticmethod
    def make_product(product_repo, quantity=10, price=19.99, name="testing"):
        return product_repo.save(
            Product(
                name=name,
                description="test_description",
                price=price,
                quantity=quantity,
            )
        )

    @staticmethod
    def make_cart_item(product_id, quantity, price=19.99):
        return CartItem(
            cart_id=uuid4(),
            product_id=product_id,
            quantity=quantity,
            product_price=price,
        )

    def test_add_product(self, session, service):
        payload = AddProduct(
            name="Test Item",
            description="test_description",
            price=19.99,
            quantity=10,
        )

        product = service.add_product(payload)

        assert product.id is not None
        assert product.name == "Test Item"
        assert product.quantity == 10
        assert session.get(Product, product.id) is not None

    @pytest.mark.parametrize("quantity", [0, -10])
    def test_invalid_quantity_for_add_product(self, quantity):
        with pytest.raises(ValidationError):
            AddProduct(
                name="Test Item",
                description="test_description",
                price=19.99,
                quantity=quantity,
            )

    @pytest.mark.parametrize("price", [0, -5.0])
    def test_invalid_price_for_add_product(self, price):
        with pytest.raises(ValidationError):
            AddProduct(
                name="Test Item",
                description="test_description",
                price=price,
                quantity=5,
            )

    def test_increase_stock(self, session, service, product_repo):
        saved_product = self.make_product(product_repo, quantity=10)

        updated = service.restock(
            UpdateProduct(
                id=saved_product.id,
                name="test_name",
                description="test_description",
                price=19.99,
                quantity=10,
            )
        )

        assert updated.quantity == 20
        assert updated.name == "test_name"

        session.expire_all()
        session.refresh(saved_product)
        assert saved_product.quantity == 20

    def test_restock_product_not_found(self, service):
        with pytest.raises(ProductNotFoundException):
            service.restock(
                UpdateProduct(
                    id=uuid4(),
                    name="test_name",
                    description="test_description",
                    price=19.99,
                    quantity=10,
                )
            )

    @pytest.mark.parametrize("quantity", [0, -10])
    def test_invalid_quantity_for_restock(self, quantity):
        with pytest.raises(ValidationError):
            UpdateProduct(
                id=uuid4(),
                name="test_name",
                description="test_description",
                price=19.99,
                quantity=quantity,
            )

    def test_dispense_reduces_stock_and_returns_total(self, session, service, product_repo):
        product = self.make_product(product_repo, quantity=10, price=5.0)

        total = service.dispense([self.make_cart_item(product.id, quantity=4, price=5.0)])

        assert total == 20.0

        session.expire_all()
        assert session.get(Product, product.id).quantity == 6

    def test_dispense_multiple_items(self, session, service, product_repo):
        first = self.make_product(product_repo, quantity=10, price=5.0, name="first")
        second = self.make_product(product_repo, quantity=5, price=2.0, name="second")

        total = service.dispense(
            [
                self.make_cart_item(first.id, quantity=2),
                self.make_cart_item(second.id, quantity=3),
            ]
        )

        assert total == 2 * 5.0 + 3 * 2.0

        session.expire_all()
        assert session.get(Product, first.id).quantity == 8
        assert session.get(Product, second.id).quantity == 2

    def test_dispense_all_stock_leaves_zero(self, session, service, product_repo):
        product = self.make_product(product_repo, quantity=10)

        service.dispense([self.make_cart_item(product.id, quantity=10)])

        session.expire_all()
        assert session.get(Product, product.id).quantity == 0

    def test_dispense_more_than_available_raises(self, service, product_repo):
        product = self.make_product(product_repo, quantity=3)

        with pytest.raises(ProductStockException):
            service.dispense([self.make_cart_item(product.id, quantity=10)])

    def test_dispense_short_on_stock_deducts_nothing(self, session, service, product_repo):
        plenty = self.make_product(product_repo, quantity=10, name="plenty")
        scarce = self.make_product(product_repo, quantity=1, name="scarce")

        with pytest.raises(ProductStockException):
            service.dispense(
                [
                    self.make_cart_item(plenty.id, quantity=4),
                    self.make_cart_item(scarce.id, quantity=2),
                ]
            )

        session.expire_all()
        assert session.get(Product, plenty.id).quantity == 10
        assert session.get(Product, scarce.id).quantity == 1

    def test_dispense_missing_product_deducts_nothing(self, session, service, product_repo):
        real = self.make_product(product_repo, quantity=10)

        with pytest.raises(ProductNotFoundException):
            service.dispense(
                [
                    self.make_cart_item(real.id, quantity=4),
                    self.make_cart_item(uuid4(), quantity=1),
                ]
            )

        session.expire_all()
        assert session.get(Product, real.id).quantity == 10

    def test_dispense_same_product_twice_cannot_exceed_stock(self, session, service, product_repo):
        product = self.make_product(product_repo, quantity=5)

        with pytest.raises(ProductStockException):
            service.dispense(
                [
                    self.make_cart_item(product.id, quantity=3),
                    self.make_cart_item(product.id, quantity=3),
                ]
            )

        session.expire_all()
        assert session.get(Product, product.id).quantity == 5

    def test_dispense_product_not_found(self, service):
        with pytest.raises(ProductNotFoundException):
            service.dispense([self.make_cart_item(uuid4(), quantity=1)])

    def test_that_delete_product_deletes_product(self, service, product_repo):
        saved = self.make_product(product_repo)

        service.delete(id=saved.id)

        assert product_repo.find_by_id(saved.id) is None

    def test_delete_product_not_found(self, service):
        with pytest.raises(ProductNotFoundException):
            service.delete(id=uuid4())

    def test_get_product_with_invalid_id_raises_not_found(self, service):
        with pytest.raises(ProductNotFoundException):
            service.get_product(uuid4())

    def test_get_product_with_valid_id(self, session, service, product_repo):
        saved = self.make_product(product_repo, name="test_name")

        found = service.get_product(id=saved.id)

        assert found.name == "test_name"
        assert session.get(Product, saved.id).id == found.id

    def test_get_all_products_empty(self, service):
        assert service.get_all_products() == []

    def test_get_all_products(self, service, product_repo):
        self.make_product(product_repo, name="first")
        self.make_product(product_repo, name="second")

        products = service.get_all_products()

        assert {p.name for p in products} == {"first", "second"}