from uuid import uuid4

import pytest
from sqlmodel import SQLModel, Session, create_engine, StaticPool, select

from app.exception.product_not_found_exception import ProductNotFoundException
from app.exception.product_stock_exception import ProductStockException
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.services.inventory_service import InventoryService
from app.services.sales_service import OrderService


class TestOrderService:

    @pytest.fixture
    def session(self):
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
    def service(self, session):
        product_repo = ProductRepository(session)
        return OrderService(
            OrderRepository(session),
            CartRepository(session),
            product_repo,
            InventoryService(product_repo),
        )

    @pytest.fixture
    def customer_id(self):
        return uuid4()

    @pytest.fixture
    def make_product(self, session):
        def _make(quantity=10, price=10.0, name="Widget"):
            product = Product(name=name, description="a product", price=price, quantity=quantity)
            session.add(product)
            session.commit()
            session.refresh(product)
            return product

        return _make

    @pytest.fixture
    def fill_cart(self, session):
        def _fill(customer_id, product, quantity):
            cart = session.exec(select(Cart).where(Cart.customer_id == customer_id)).first()
            if cart is None:
                cart = Cart(customer_id=customer_id)
                session.add(cart)
                session.commit()
                session.refresh(cart)
            session.add(CartItem(
                cart_id=cart.id, product_id=product.id,
                quantity=quantity, product_price=product.price,
            ))
            session.commit()

        return _fill

    def test_checkout_creates_order_deducts_stock_and_empties_cart(
        self, session, service, customer_id, make_product, fill_cart
    ):
        product = make_product(quantity=10, price=5.0)
        fill_cart(customer_id, product, 3)

        order = service.create_order(customer_id)

        assert order.total_amount == 15.0
        assert order.status == OrderStatus.PENDING
        assert len(order.items) == 1
        session.expire_all()
        assert session.get(Product, product.id).quantity == 7
        assert session.exec(select(CartItem)).all() == []

    def test_checkout_uses_current_price_when_price_changed(
        self, session, service, customer_id, make_product, fill_cart
    ):
        product = make_product(quantity=10, price=5.0)
        fill_cart(customer_id, product, 3)

        product.price = 8.0
        session.add(product)
        session.commit()

        order = service.create_order(customer_id)

        assert order.total_amount == 24.0
        assert order.items[0].price_purchased == 8.0

    def test_checkout_with_empty_cart_raises(self, service, customer_id):
        with pytest.raises(ValueError, match="empty cart"):
            service.create_order(customer_id)

    def test_checkout_short_on_stock_deducts_nothing(
        self, session, service, customer_id, make_product, fill_cart
    ):
        plenty = make_product(quantity=10, name="Plenty")
        scarce = make_product(quantity=1, name="Scarce")
        fill_cart(customer_id, plenty, 4)
        fill_cart(customer_id, scarce, 2)

        with pytest.raises(ProductStockException):
            service.create_order(customer_id)

        session.expire_all()
        assert session.get(Product, plenty.id).quantity == 10
        assert session.get(Product, scarce.id).quantity == 1
        assert session.exec(select(Order)).all() == []
        assert len(session.exec(select(CartItem)).all()) == 2

    def test_get_order_hides_other_customers_orders(
        self, service, customer_id, make_product, fill_cart
    ):
        product = make_product()
        fill_cart(customer_id, product, 1)
        order = service.create_order(customer_id)

        with pytest.raises(ValueError, match="Order not found"):
            service.get_order(uuid4(), order.id)

    def test_cancel_restores_stock(self, session, service, customer_id, make_product, fill_cart):
        product = make_product(quantity=10)
        fill_cart(customer_id, product, 4)
        order = service.create_order(customer_id)

        cancelled = service.cancel_order(customer_id, order.id)

        assert cancelled.status == OrderStatus.CANCELLED
        session.expire_all()
        assert session.get(Product, product.id).quantity == 10

    def test_cancel_twice_is_refused_and_restocks_once(
        self, session, service, customer_id, make_product, fill_cart
    ):
        product = make_product(quantity=10)
        fill_cart(customer_id, product, 4)
        order = service.create_order(customer_id)
        service.cancel_order(customer_id, order.id)

        with pytest.raises(ValueError, match="already cancelled"):
            service.cancel_order(customer_id, order.id)

        session.expire_all()
        assert session.get(Product, product.id).quantity == 10   # not 14

    def test_cancel_someone_elses_order_is_refused(
        self, session, service, customer_id, make_product, fill_cart
    ):
        product = make_product(quantity=10)
        fill_cart(customer_id, product, 4)
        order = service.create_order(customer_id)

        with pytest.raises(ValueError, match="Order not found"):
            service.cancel_order(uuid4(), order.id)

        session.expire_all()
        assert session.get(Product, product.id).quantity == 6


class TestCartPriceRefresh:
    @pytest.fixture
    def session(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            yield session
        SQLModel.metadata.drop_all(engine)

    def test_get_cart_updates_stale_price_and_total(self, session):
        from app.models.cart import CreateCart
        from app.services.cart_service import CartService

        product = Product(name="Mug", description="cup", price=5.0, quantity=10)
        session.add(product)
        session.commit()
        session.refresh(product)

        customer_id = uuid4()
        service = CartService(CartRepository(session), ProductRepository(session))
        service.add_item_to_cart(customer_id, CreateCart(product_id=product.id, quantity=2))

        product.price = 9.0
        session.add(product)
        session.commit()

        cart = service.get_cart(customer_id)

        assert cart.items[0].product_price == 9.0
        assert cart.total_price == 18.0
        session.expire_all()
        assert session.exec(select(CartItem)).first().product_price == 9.0