from uuid import UUID, uuid4

import pytest
from sqlmodel import select

from app.enums.user_role import UserRole
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.routers.sales_router import router as sales_router


class TestSalesRouterRBAC:

    @pytest.fixture
    def client(self, make_client):
        return make_client(sales_router)

    @pytest.fixture
    def customer(self, make_user):
        return make_user(UserRole.CUSTOMER, "customer@gmail.com")

    @pytest.fixture
    def other_customer(self, make_user):
        return make_user(UserRole.CUSTOMER, "other@gmail.com")

    @pytest.fixture
    def storekeeper(self, make_user):
        return make_user(UserRole.STOREKEEPER, "keeper@gmail.com")

    @pytest.fixture
    def fill_cart(self, session):
        """Put `quantity` of `product` into the customer's cart directly in the DB."""

        def _fill(customer, product, quantity):
            cart = session.exec(select(Cart).where(Cart.customer_id == customer.id)).first()
            if cart is None:
                cart = Cart(customer_id=customer.id)
                session.add(cart)
                session.commit()
                session.refresh(cart)
            session.add(
                CartItem(
                    cart_id=cart.id,
                    product_id=product.id,
                    quantity=quantity,
                    product_price=product.price,
                )
            )
            session.commit()

        return _fill

    @pytest.fixture
    def checkout(self, client, auth_header, make_product, fill_cart):
        def _checkout(customer, quantity=2, stock=10, price=10.0):
            product = make_product(quantity=stock, price=price)
            fill_cart(customer, product, quantity)
            response = client.post("/sales/orders", headers=auth_header(customer))
            return product, response

        return _checkout

    @staticmethod
    def all_routes():
        order_id = uuid4()
        return [
            ("post", "/sales/orders"),
            ("get", "/sales/orders"),
            ("get", f"/sales/orders/{order_id}"),
            ("post", f"/sales/orders/{order_id}/cancel"),
        ]

    # ---------- 401 / 403 ----------

    def test_all_routes_reject_missing_token(self, client):
        for method, url in self.all_routes():
            assert client.request(method, url).status_code == 401, f"{method.upper()} {url}"

    def test_all_routes_forbid_storekeeper(self, client, storekeeper, auth_header):
        for method, url in self.all_routes():
            response = client.request(method, url, headers=auth_header(storekeeper))
            assert response.status_code == 403, f"{method.upper()} {url}"

    # ---------- checkout ----------

    def test_customer_can_check_out(self, session, customer, checkout):
        product, response = checkout(customer, quantity=2, stock=10, price=10.0)

        assert response.status_code == 201
        body = response.json()
        assert body["customer_id"] == str(customer.id)
        assert body["total_amount"] == 20.0
        assert body["status"] == OrderStatus.PENDING.value

        session.expire_all()
        assert session.get(Product, product.id).quantity == 8
        assert session.exec(select(CartItem)).all() == []

    def test_checkout_uses_token_user_even_if_body_names_someone_else(
        self, client, session, customer, other_customer, make_product, fill_cart, auth_header
    ):
        product = make_product()
        fill_cart(customer, product, 1)

        response = client.post(
            "/sales/orders",
            json={"customer_id": str(other_customer.id), "cart_id": str(uuid4())},
            headers=auth_header(customer),
        )

        assert response.status_code == 201
        assert response.json()["customer_id"] == str(customer.id)
        assert session.exec(select(Order).where(Order.customer_id == other_customer.id)).first() is None

    def test_checkout_with_empty_cart_returns_400(self, client, customer, auth_header):
        response = client.post("/sales/orders", headers=auth_header(customer))

        assert response.status_code == 400

    # ---------- viewing orders ----------

    def test_customer_can_get_own_order(self, client, customer, checkout, auth_header):
        _, created = checkout(customer)
        order_id = created.json()["id"]

        response = client.get(f"/sales/orders/{order_id}", headers=auth_header(customer))

        assert response.status_code == 200
        assert response.json()["id"] == order_id

    def test_customer_cannot_get_someone_elses_order(self, client, customer, other_customer, checkout, auth_header):
        _, created = checkout(customer)

        response = client.get(f"/sales/orders/{created.json()['id']}", headers=auth_header(other_customer))

        assert response.status_code == 404

    def test_list_orders_only_returns_own_orders(self, client, customer, other_customer, checkout, auth_header):
        checkout(customer)
        checkout(other_customer)

        mine = client.get("/sales/orders", headers=auth_header(customer))

        assert mine.status_code == 200
        assert len(mine.json()) == 1
        assert mine.json()[0]["customer_id"] == str(customer.id)

    # ---------- checkout problems ----------

    def test_checkout_with_not_enough_stock_is_400_and_changes_nothing(
        self, client, session, make_product, fill_cart, customer, auth_header
    ):
        plenty = make_product(quantity=10, name="Plenty")
        scarce = make_product(quantity=1, name="Scarce")
        fill_cart(customer, plenty, 3)
        fill_cart(customer, scarce, 5)

        response = client.post("/sales/orders", headers=auth_header(customer))

        assert response.status_code == 400
        assert "Scarce" in response.json()["detail"]
        session.expire_all()
        assert session.get(Product, plenty.id).quantity == 10   # not deducted
        assert session.get(Product, scarce.id).quantity == 1
        assert session.exec(select(Order)).first() is None

    # ---------- cancelling ----------

    def test_cancelling_twice_is_409_and_restocks_only_once(self, client, session, customer, checkout, auth_header):
        product, created = checkout(customer, quantity=2, stock=10)
        url = f"/sales/orders/{created.json()['id']}/cancel"

        first = client.post(url, headers=auth_header(customer))
        second = client.post(url, headers=auth_header(customer))

        assert first.status_code == 200
        assert second.status_code == 409
        assert "already cancelled" in second.json()["detail"]
        session.expire_all()
        assert session.get(Product, product.id).quantity == 10   # not 12

    def test_customer_can_cancel_own_order_and_stock_is_restored(self, client, session, customer, checkout, auth_header):
        product, created = checkout(customer, quantity=2, stock=10)

        response = client.post(f"/sales/orders/{created.json()['id']}/cancel", headers=auth_header(customer))

        assert response.status_code == 200
        assert response.json()["status"] == OrderStatus.CANCELLED.value
        session.expire_all()
        assert session.get(Product, product.id).quantity == 10

    def test_customer_cannot_cancel_someone_elses_order(self, client, session, customer, other_customer, checkout, auth_header):
        product, created = checkout(customer, quantity=2, stock=10)

        response = client.post(f"/sales/orders/{created.json()['id']}/cancel", headers=auth_header(other_customer))

        assert response.status_code == 409
        session.expire_all()
        assert session.get(Product, product.id).quantity == 8
        assert session.get(Order, UUID(created.json()["id"])).status == OrderStatus.PENDING