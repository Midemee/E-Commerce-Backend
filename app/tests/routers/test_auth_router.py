import pytest
from sqlmodel import select

from app.enums.user_role import UserRole
from app.models.user import User
from app.routers.auth_router import router as auth_router
from app.routers.inventory_router import router as inventory_router

PASSWORD = "test-password"


class TestSingleRegisterAndLogin:

    @pytest.fixture
    def client(self, make_client):
        return make_client(auth_router, inventory_router)

    @staticmethod
    def register(client, email="john@gmail.com", **extra):
        body = {"name": "John", "email": email, "password": PASSWORD}
        body.update(extra)
        return client.post("/auth/register", json=body)

    @staticmethod
    def login(client, email="john@gmail.com", password=PASSWORD):
        return client.post("/auth/login", json={"email": email, "password": password})

    def token_for(self, client, email="john@gmail.com"):
        self.register(client, email)
        return self.login(client, email).json()["access_token"]

    @staticmethod
    def bearer(token):
        return {"Authorization": f"Bearer {token}"}

    # ---------- register ----------

    def test_register_creates_a_customer(self, client, session):
        response = self.register(client)

        assert response.status_code == 201
        assert response.json()["role"] == "CUSTOMER"
        assert response.json()["email"] == "john@gmail.com"
        assert "password" not in response.json()

        saved = session.exec(select(User).where(User.email == "john@gmail.com")).one()
        assert saved.role == UserRole.CUSTOMER

    def test_register_ignores_a_role_sent_by_the_client(self, client, session):
        response = self.register(client, role="STOREKEEPER")

        assert response.status_code == 201
        assert response.json()["role"] == "CUSTOMER"

        saved = session.exec(select(User)).one()
        assert saved.role == UserRole.CUSTOMER

    def test_duplicate_email_is_conflict(self, client):
        self.register(client)

        assert self.register(client).status_code == 409

    def test_short_password_is_rejected(self, client, session):
        response = client.post(
            "/auth/register",
            json={"name": "John", "email": "john@gmail.com", "password": "short"},
        )

        assert response.status_code == 422
        assert session.exec(select(User)).first() is None

    # ---------- login ----------

    def test_login_returns_token_and_role(self, client):
        self.register(client)

        response = self.login(client)

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["user"]["role"] == "CUSTOMER"
        assert body["user"]["email"] == "john@gmail.com"

    def test_wrong_password_and_unknown_email_look_the_same(self, client):
        self.register(client)

        wrong_password = self.login(client, password="wrong-password")
        unknown_email = self.login(client, email="nobody@gmail.com")

        assert wrong_password.status_code == 401
        assert unknown_email.status_code == 401
        assert wrong_password.json()["detail"] == unknown_email.json()["detail"]

    def test_old_role_specific_endpoints_are_gone(self, client):
        body = {"name": "John", "email": "john@gmail.com", "password": PASSWORD}

        for url in (
            "/auth/customers/register",
            "/auth/customers/login",
            "/auth/storekeepers/register",
            "/auth/storekeepers/login",
        ):
            assert client.post(url, json=body).status_code == 404, url

    # ---------- /auth/me ----------

    def test_me_requires_a_token(self, client):
        assert client.get("/auth/me").status_code == 401

    def test_me_returns_the_logged_in_user(self, client):
        token = self.token_for(client)

        response = client.get("/auth/me", headers=self.bearer(token))

        assert response.status_code == 200
        assert response.json()["email"] == "john@gmail.com"
        assert response.json()["role"] == "CUSTOMER"
        assert "password" not in response.json()

    # ---------- promote ----------

    def test_promote_requires_a_token(self, client):
        self.register(client)

        response = client.post("/auth/promote", json={"email": "john@gmail.com"})

        assert response.status_code == 401

    def test_customer_cannot_promote_anyone(self, client, session):
        token = self.token_for(client)

        response = client.post(
            "/auth/promote",
            json={"email": "john@gmail.com"},
            headers=self.bearer(token),
        )

        assert response.status_code == 403
        session.expire_all()
        assert session.exec(select(User)).one().role == UserRole.CUSTOMER

    def test_storekeeper_can_promote_a_customer(self, client, session, make_user):
        make_user(UserRole.STOREKEEPER, "boss@gmail.com")
        boss_token = self.login(client, "boss@gmail.com", "test-password").json()["access_token"]
        self.register(client)

        response = client.post(
            "/auth/promote",
            json={"email": "john@gmail.com"},
            headers=self.bearer(boss_token),
        )

        assert response.status_code == 200
        assert response.json()["role"] == "STOREKEEPER"

        session.expire_all()
        john = session.exec(select(User).where(User.email == "john@gmail.com")).one()
        assert john.role == UserRole.STOREKEEPER

    def test_promote_unknown_email_is_404(self, client, make_user):
        make_user(UserRole.STOREKEEPER, "boss@gmail.com")
        boss_token = self.login(client, "boss@gmail.com", "test-password").json()["access_token"]

        response = client.post(
            "/auth/promote",
            json={"email": "nobody@gmail.com"},
            headers=self.bearer(boss_token),
        )

        assert response.status_code == 404

    # ---------- the whole story ----------

    def test_register_login_then_promoted_gets_storekeeper_access(self, client, session):
        token = self.token_for(client)
        headers = self.bearer(token)

        new_product = {"name": "Widget", "description": "a widget", "price": 5, "quantity": 2}

        # A brand-new account is only a customer: it can look, but not create.
        assert client.get("/inventory/get_all_products", headers=headers).status_code == 200
        assert client.post("/inventory/create_product", json=new_product, headers=headers).status_code == 403

        # Promoted by hand (this is what the command-line script does).
        user = session.exec(select(User)).one()
        user.role = UserRole.STOREKEEPER
        session.add(user)
        session.commit()

        # The SAME token now works: the role is read from the database on every request.
        assert client.post("/inventory/create_product", json=new_product, headers=headers).status_code == 201
        assert client.get("/auth/me", headers=headers).json()["role"] == "STOREKEEPER"

        # And a fresh login reports the new role to the frontend.
        assert self.login(client).json()["user"]["role"] == "STOREKEEPER"