from uuid import uuid4

import pytest
from sqlmodel import select

from app.enums.user_role import UserRole
from app.models.cart import Cart, CartItem
from app.routers.cart_router import router as cart_router


class TestCartRouterRBAC:

    @pytest.fixture
    def client(self, make_client):
        return make_client(cart_router)

    @pytest.fixture
    def customer(self, make_user):
        return make_user(UserRole.CUSTOMER, "customer@gmail.com")

    @pytest.fixture
    def other_customer(self, make_user):
        return make_user(UserRole.CUSTOMER, "other@gmail.com")

    @pytest.fixture
    def storekeeper(self, make_user):
        return make_user(UserRole.STOREKEEPER, "keeper@gmail.com")

    @staticmethod
    def all_routes(product_id):
        return [
            ("post", "/cart-service/add_product_to_cart", {"product_id": str(product_id), "quantity": 1}),
            ("get", "/cart-service/find_cart", None),
            ("delete", f"/cart-service/clear_items_from_cart?cart_id={uuid4()}", None),
            ("delete", "/cart-service/clear_cart", None),
        ]

    # ---------- 401 / 403 ----------

    def test_all_routes_reject_missing_token(self, client, make_product):
        product = make_product()

        for method, url, body in self.all_routes(product.id):
            response = client.request(method, url, json=body)
            assert response.status_code == 401, f"{method.upper()} {url}"

    def test_all_routes_forbid_storekeeper(self, client, make_product, storekeeper, auth_header):
        product = make_product()

        for method, url, body in self.all_routes(product.id):
            response = client.request(method, url, json=body, headers=auth_header(storekeeper))
            assert response.status_code == 403, f"{method.upper()} {url}"
            assert response.json()["detail"] == "Customer access required"

    # ---------- customer happy path ----------

    def test_customer_can_add_product_to_cart(self, client, session, make_product, customer, auth_header):
        product = make_product(quantity=5, price=10.0)

        response = client.post(
            "/cart-service/add_product_to_cart",
            json={"product_id": str(product.id), "quantity": 2},
            headers=auth_header(customer),
        )

        assert response.status_code == 201
        # The cart belongs to the token's user, not to anything the client sent.
        assert response.json()["customer_id"] == str(customer.id)

        cart = session.exec(select(Cart).where(Cart.customer_id == customer.id)).one()
        items = session.exec(select(CartItem).where(CartItem.cart_id == cart.id)).all()
        assert [(i.product_id, i.quantity, i.product_price) for i in items] == [(product.id, 2, 10.0)]

    def test_customer_id_sent_by_client_is_ignored(self, client, session, make_product, customer, other_customer, auth_header):
        product = make_product()

        client.post(
            f"/cart-service/add_product_to_cart?customer_id={other_customer.id}",
            json={"product_id": str(product.id), "quantity": 1, "customer_id": str(other_customer.id)},
            headers=auth_header(customer),
        )

        assert session.exec(select(Cart).where(Cart.customer_id == other_customer.id)).first() is None
        assert session.exec(select(Cart).where(Cart.customer_id == customer.id)).first() is not None

    def test_add_more_than_stock_returns_400(self, client, make_product, customer, auth_header):
        product = make_product(quantity=1)

        response = client.post(
            "/cart-service/add_product_to_cart",
            json={"product_id": str(product.id), "quantity": 5},
            headers=auth_header(customer),
        )

        assert response.status_code == 400

    def test_find_cart_returns_own_cart(self, client, customer, auth_header):
        response = client.get("/cart-service/find_cart", headers=auth_header(customer))

        assert response.status_code == 200
        assert response.json()["customer_id"] == str(customer.id)

    def test_customers_have_separate_carts(self, client, customer, other_customer, auth_header):
        mine = client.get("/cart-service/find_cart", headers=auth_header(customer)).json()
        theirs = client.get("/cart-service/find_cart", headers=auth_header(other_customer)).json()

        assert mine["id"] != theirs["id"]

    def test_customer_cannot_remove_item_from_someone_elses_cart(
        self, client, session, make_product, customer, other_customer, auth_header
    ):
        product = make_product()
        client.post(
            "/cart-service/add_product_to_cart",
            json={"product_id": str(product.id), "quantity": 1},
            headers=auth_header(other_customer),
        )
        victim_item = session.exec(select(CartItem)).one()

        response = client.delete(
            f"/cart-service/clear_items_from_cart?cart_id={victim_item.id}",
            headers=auth_header(customer),
        )

        assert response.status_code == 404
        session.expire_all()
        assert session.get(CartItem, victim_item.id) is not None

    def test_removing_an_item_that_does_not_exist_is_404(self, client, customer, auth_header):
        response = client.delete(
            f"/cart-service/clear_items_from_cart?cart_id={uuid4()}",
            headers=auth_header(customer),
        )

        assert response.status_code == 404

    def test_clearing_a_cart_that_was_never_created_is_fine(self, client, customer, auth_header):
        response = client.delete("/cart-service/clear_cart", headers=auth_header(customer))

        assert response.status_code == 204

    def test_customer_can_clear_own_cart(self, client, session, make_product, customer, auth_header):
        product = make_product()
        client.post(
            "/cart-service/add_product_to_cart",
            json={"product_id": str(product.id), "quantity": 1},
            headers=auth_header(customer),
        )

        response = client.delete("/cart-service/clear_cart", headers=auth_header(customer))

        assert response.status_code == 204
        assert session.exec(select(CartItem)).all() == []