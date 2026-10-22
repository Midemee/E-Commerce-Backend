from app.exception import AuthenticationException, UserNotFoundException
from app.repositories.user_repository import UserRepository

from app.models.user import (
    User,
    RegisterUser,
    LoginUser,
    UserResponse,
    LoginResponse
)

from app.enums.user_role import UserRole

from app.security.password import (
    hash_password,
    verify_password
)

from app.security.token import create_access_token


class AuthService:

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def register(
        self,
        payload: RegisterUser
    ) -> UserResponse:

        if self.user_repository.exists_by_email(
            payload.email
        ):
            raise AuthenticationException(
                "An account with this email already exists"
            )

        user = User(
            name=payload.name,
            email=payload.email,
            password=hash_password(payload.password),
            role=UserRole.CUSTOMER
        )

        user = self.user_repository.save(user)

        return UserResponse.model_validate(user)

    def login(
        self,
        payload: LoginUser
    ) -> LoginResponse:

        found_user = self.user_repository.find_by_email(
            payload.email
        )

        if found_user is None or not verify_password(
            payload.password,
            found_user.password
        ):
            raise AuthenticationException(
                "Invalid email or password"
            )

        access_token = create_access_token(
            user_id=str(found_user.id)
        )

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.model_validate(found_user)
        )

    def promote_to_storekeeper(
        self,
        email: str
    ) -> UserResponse:

        user = self.user_repository.find_by_email(email)

        if user is None:
            raise UserNotFoundException(
                "No account exists with this email"
            )

        if user.role != UserRole.STOREKEEPER:
            user.role = UserRole.STOREKEEPER
            user = self.user_repository.save(user)

        return UserResponse.model_validate(user)