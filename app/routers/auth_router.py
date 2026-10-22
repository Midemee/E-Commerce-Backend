from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.config.dependencies import get_session
from app.exception import AuthenticationException, UserNotFoundException
from app.repositories.user_repository import UserRepository
from app.security.dependencies import get_current_user, require_storekeeper
from app.services.auth_service import AuthService

from app.models.user import (User, RegisterUser, LoginUser, PromoteUser, UserResponse,LoginResponse)

router = APIRouter(prefix="/auth",tags=["auth"])

def get_auth_service(
    session: Session = Depends(get_session)
) -> AuthService:

    user_repository = UserRepository(session)
    return AuthService(user_repository)

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register(
    payload: RegisterUser,
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        return auth_service.register(payload)

    except AuthenticationException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.post(
    "/login",
    response_model=LoginResponse
)
def login(
    payload: LoginUser,
    auth_service: AuthService = Depends(get_auth_service)
):

    try:
        return auth_service.login(payload)

    except AuthenticationException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

@router.get(
    "/me",
    response_model=UserResponse
)
def me(
    current_user: User = Depends(get_current_user)
):

    return current_user

@router.post(
    "/promote",
    response_model=UserResponse
)
def promote_to_storekeeper(
    payload: PromoteUser,
    _current_user: User = Depends(require_storekeeper),
    auth_service: AuthService = Depends(get_auth_service)
):

    try:
        return auth_service.promote_to_storekeeper(payload.email)

    except UserNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )