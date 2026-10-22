import pytest

from jwt import decode
from sqlmodel import SQLModel, create_engine, Session, select, StaticPool

from app.exception import AuthenticationException, UserNotFoundException
from app.enums.user_role import UserRole

from app.models.user import (User, RegisterUser, LoginUser, LoginResponse)

from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService

from app.security.password import verify_password
from app.security.token import SECRET_KEY, ALGORITHM


class TestAuthService:

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
    def auth_service(self, session):
        return AuthService(UserRepository(session))

    @staticmethod
    def register_john(auth_service):
        return auth_service.register(
            RegisterUser(
                name="John",
                email="john@gmail.com",
                password="test-password"
            )
        )

    def test_register_creates_a_customer(self, session, auth_service):
        response = self.register_john(auth_service)

        assert response.id is not None
        assert response.name == "John"
        assert response.email == "john@gmail.com"
        assert response.role == UserRole.CUSTOMER

        user = session.get(User, response.id)

        assert user is not None
        assert user.role == UserRole.CUSTOMER

    def test_register_hashes_the_password(self, session, auth_service):
        response = self.register_john(auth_service)

        user = session.get(User, response.id)

        assert user.password != "test-password"
        assert verify_password("test-password", user.password)

    def test_register_fails_when_email_exists(self, session, auth_service):
        self.register_john(auth_service)

        with pytest.raises(
            AuthenticationException,
            match="An account with this email already exists"
        ):
            self.register_john(auth_service)

        assert len(session.exec(select(User)).all()) == 1

    def test_register_never_creates_a_storekeeper(self, auth_service):
        assert self.register_john(auth_service).role == UserRole.CUSTOMER

    def test_login(self, auth_service):
        self.register_john(auth_service)

        response = auth_service.login(
            LoginUser(email="john@gmail.com", password="test-password")
        )

        assert isinstance(response, LoginResponse)
        assert response.token_type == "bearer"
        assert len(response.access_token) > 0

        assert response.user.id is not None
        assert response.user.name == "John"
        assert response.user.email == "john@gmail.com"
        assert response.user.role == UserRole.CUSTOMER

    def test_login_token_holds_the_user_id(self, auth_service):
        registered = self.register_john(auth_service)

        response = auth_service.login(
            LoginUser(email="john@gmail.com", password="test-password")
        )

        payload = decode(response.access_token, SECRET_KEY, algorithms=[ALGORITHM])

        assert payload["sub"] == str(registered.id)

    def test_login_fails_when_email_does_not_exist(self, auth_service):
        with pytest.raises(
            AuthenticationException,
            match="Invalid email or password"
        ):
            auth_service.login(
                LoginUser(email="fake@gmail.com", password="test-password")
            )

    def test_login_fails_when_password_is_wrong(self, auth_service):
        self.register_john(auth_service)

        with pytest.raises(
            AuthenticationException,
            match="Invalid email or password"
        ):
            auth_service.login(
                LoginUser(email="john@gmail.com", password="wrong-password")
            )

    def test_promote_to_storekeeper(self, session, auth_service):
        registered = self.register_john(auth_service)

        response = auth_service.promote_to_storekeeper("john@gmail.com")

        assert response.id == registered.id
        assert response.role == UserRole.STOREKEEPER

        session.expire_all()
        assert session.get(User, registered.id).role == UserRole.STOREKEEPER

    def test_promote_unknown_email_raises(self, auth_service):
        with pytest.raises(UserNotFoundException):
            auth_service.promote_to_storekeeper("nobody@gmail.com")

    def test_promote_is_safe_to_repeat(self, auth_service):
        self.register_john(auth_service)

        auth_service.promote_to_storekeeper("john@gmail.com")
        again = auth_service.promote_to_storekeeper("john@gmail.com")

        assert again.role == UserRole.STOREKEEPER

    def test_promoted_user_logs_in_with_the_same_login(self, auth_service):
        self.register_john(auth_service)
        auth_service.promote_to_storekeeper("john@gmail.com")

        response = auth_service.login(
            LoginUser(email="john@gmail.com", password="test-password")
        )

        assert response.user.role == UserRole.STOREKEEPER

    def test_promote_does_not_touch_other_users(self, session, auth_service):
        self.register_john(auth_service)
        auth_service.register(
            RegisterUser(name="Mary", email="mary@gmail.com", password="test-password")
        )

        auth_service.promote_to_storekeeper("john@gmail.com")

        mary = session.exec(select(User).where(User.email == "mary@gmail.com")).one()
        assert mary.role == UserRole.CUSTOMER