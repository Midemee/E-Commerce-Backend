from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, StaticPool

from app.config.dependencies import get_session
from app.enums.user_role import UserRole
from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.models.user import User
from app.routers.inventory_router import router as inventory_router
from app.security.password import hash_password
from app.security.token import create_access_token


class TestInventoryRouterRBAC:
    """
    Exercises the full dependency flow:
    oauth2_scheme -> get_current_user -> require_storekeeper -> route.
    """

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
    def client(self, session):
        app = FastAPI()
        app.include_router(inventory_router)
        app.dependency_overrides[get_session] = lambda: session
        with TestClient(app) as test_client:
            yield test_client

    @staticmethod
    def make_user(session, role: UserRole, email: str) -> User:
        user = User(
            name="Test User",
            email=email,
            password=hash_password("test-password"),
            role=role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def auth_header(user: User) -> dict:
        token = create_access_token(user_id=str(user.id))
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture
    def storekeeper_headers(self, session):
        user = self.make_user(session, UserRole.STOREKEEPER, "keeper@gmail.com")
        return self.auth_header(user)

    @pytest.fixture
    def customer_headers(self, session):
        user = self.make_user(session, UserRole.CUSTOMER, "customer@gmail.com")
        return self.auth_header(user)

    @pytest.fixture
    def product(self, session) -> Product:
        product = Product(
            name="Test Product",
            description="test_description",
            price=10.0,
            quantity=5,
        )
        session.add(product)
        session.commit()
        session.refresh(product)
        return product

    # Every protected route as (method, url, json-body-factory)
    @staticmethod
    def protected_routes(product_id):
        return [
            ("post", "/inventory/create_product", {
                "name": "New Item", "description": "new_description",
                "price": 9.99, "quantity": 3,
            }),
            ("post", "/inventory/update_product", {
                "id": str(product_id), "name": "Updated", "description": "updated_description",
                "price": 9.99, "quantity": 3,
            }),
            ("get", "/inventory/get_all_products", None),
            ("get", f"/inventory/get_product?id={product_id}", None),
            ("delete", f"/inventory/delete_product?id={product_id}", None),
        ]

    # ---------- 401: no / bad token ----------

    def test_all_routes_reject_missing_token(self, client, product):
        for method, url, body in self.protected_routes(product.id):
            response = client.request(method, url, json=body)
            assert response.status_code == 401, f"{method.upper()} {url}"

    def test_all_routes_reject_invalid_token(self, client, product):
        headers = {"Authorization": "Bearer not-a-real-token"}

        for method, url, body in self.protected_routes(product.id):
            response = client.request(method, url, json=body, headers=headers)
            assert response.status_code == 401, f"{method.upper()} {url}"

    def test_token_for_deleted_user_is_rejected(self, client, session):
        user = self.make_user(session, UserRole.STOREKEEPER, "ghost@gmail.com")
        headers = self.auth_header(user)
        session.delete(user)
        session.commit()

        response = client.get("/inventory/get_all_products", headers=headers)

        assert response.status_code == 401

    # ---------- 403: authenticated but wrong role ----------

    @staticmethod
    def write_routes(routes):
        return [r for r in routes if r[0] in ("post", "delete")]

    def test_write_routes_forbid_customer(self, client, product, customer_headers):
        for method, url, body in self.write_routes(self.protected_routes(product.id)):
            response = client.request(method, url, json=body, headers=customer_headers)
            assert response.status_code == 403, f"{method.upper()} {url}"
            assert response.json()["detail"] == "Storekeeper access required"

    def test_customer_can_browse_products(self, client, product, customer_headers):
        listing = client.get("/inventory/get_all_products", headers=customer_headers)
        single = client.get(f"/inventory/get_product?id={product.id}", headers=customer_headers)

        assert listing.status_code == 200
        assert [p["id"] for p in listing.json()] == [str(product.id)]
        assert single.status_code == 200
        assert single.json()["name"] == "Test Product"

    def test_forbidden_customer_cannot_change_stock(self, client, session, product, customer_headers):
        client.delete(f"/inventory/delete_product?id={product.id}", headers=customer_headers)

        session.expire_all()
        assert session.get(Product, product.id) is not None

    # ---------- 2xx: storekeeper ----------

    def test_storekeeper_can_create_product(self, client, session, storekeeper_headers):
        response = client.post(
            "/inventory/create_product",
            json={"name": "New Item", "description": "new_description", "price": 9.99, "quantity": 3},
            headers=storekeeper_headers,
        )

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "New Item"
        assert body["quantity"] == 3
        assert session.get(Product, UUID(body["id"])) is not None

    def test_storekeeper_can_restock_product(self, client, session, product, storekeeper_headers):
        response = client.post(
            "/inventory/update_product",
            json={
                "id": str(product.id), "name": "Updated", "description": "updated_description",
                "price": 12.5, "quantity": 5,
            },
            headers=storekeeper_headers,
        )

        assert response.status_code == 202
        assert response.json()["quantity"] == 10
        assert response.json()["name"] == "Updated"

    def test_storekeeper_can_get_all_products(self, client, product, storekeeper_headers):
        response = client.get("/inventory/get_all_products", headers=storekeeper_headers)

        assert response.status_code == 200
        assert [p["id"] for p in response.json()] == [str(product.id)]

    def test_storekeeper_can_get_product(self, client, product, storekeeper_headers):
        response = client.get(f"/inventory/get_product?id={product.id}", headers=storekeeper_headers)

        assert response.status_code == 200
        assert response.json()["name"] == "Test Product"

    def test_storekeeper_can_delete_product(self, client, session, product, storekeeper_headers):
        response = client.delete(f"/inventory/delete_product?id={product.id}", headers=storekeeper_headers)

        assert response.status_code == 204

        session.expire_all()
        assert session.get(Product, product.id) is None

    # ---------- error mapping for an authorised storekeeper ----------

    def test_get_unknown_product_returns_404(self, client, storekeeper_headers):
        response = client.get(f"/inventory/get_product?id={uuid4()}", headers=storekeeper_headers)

        assert response.status_code == 404

    def test_delete_unknown_product_returns_404(self, client, storekeeper_headers):
        response = client.delete(f"/inventory/delete_product?id={uuid4()}", headers=storekeeper_headers)

        assert response.status_code == 404

    def test_restock_unknown_product_returns_404(self, client, storekeeper_headers):
        response = client.post(
            "/inventory/update_product",
            json={
                "id": str(uuid4()), "name": "Updated", "description": "updated_description",
                "price": 12.5, "quantity": 5,
            },
            headers=storekeeper_headers,
        )

        assert response.status_code == 404

    def test_create_product_with_invalid_quantity_returns_422(self, client, storekeeper_headers):
        response = client.post(
            "/inventory/create_product",
            json={"name": "New Item", "description": "new_description", "price": 9.99, "quantity": 0},
            headers=storekeeper_headers,
        )

        assert response.status_code == 422