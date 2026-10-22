from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlmodel import Session

from app.config.dependencies import get_session
from app.enums.user_role import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.security.token import SECRET_KEY, ALGORITHM

bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session)
) -> User:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={
            "WWW-Authenticate": "Bearer"
        }
    )

    if credentials is None:
        raise credentials_exception

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise credentials_exception

        user_uuid = UUID(user_id)

    except (InvalidTokenError, ValueError):
        raise credentials_exception

    user_repository = UserRepository(session)

    user = user_repository.find_by_id(user_uuid)

    if user is None:
        raise credentials_exception

    return user


def require_customer(
    current_user: User = Depends(get_current_user)
) -> User:

    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer access required"
        )

    return current_user


def require_storekeeper(
    current_user: User = Depends(get_current_user)
) -> User:

    if current_user.role != UserRole.STOREKEEPER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Storekeeper access required"
        )
    return current_user