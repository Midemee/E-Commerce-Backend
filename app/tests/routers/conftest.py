import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, StaticPool

from app.config.dependencies import get_session
from app.enums.user_role import UserRole
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.security.password import hash_password
from app.security.token import create_access_token


@pytest.fixture
def session():
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
def make_client(session):
    """Build a TestClient around the given routers, using the test session."""

    def _make(*routers, overrides=None):
        app = FastAPI()
        for router in routers:
            app.include_router(router)
        app.dependency_overrides[get_session] = lambda: session
        for dependency, replacement in (overrides or {}).items():
            app.dependency_overrides[dependency] = replacement
        return TestClient(app)

    return _make


@pytest.fixture
def make_user(session):
    def _make(role: UserRole, email: str) -> User:
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

    return _make


@pytest.fixture
def auth_header():
    def _header(user: User) -> dict:
        token = create_access_token(user_id=str(user.id))
        return {"Authorization": f"Bearer {token}"}

    return _header


@pytest.fixture
def make_product(session):
    def _make(quantity: int = 10, price: float = 10.0, name: str = "Test Product") -> Product:
        product = Product(
            name=name,
            description="test_description",
            price=price,
            quantity=quantity,
        )
        session.add(product)
        session.commit()
        session.refresh(product)
        return product

    return _make