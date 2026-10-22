from uuid import UUID, uuid4
from pydantic import EmailStr, Field, BaseModel
from sqlmodel import SQLModel, Field as SQLField

from app.enums.user_role import UserRole


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = SQLField(default_factory=uuid4, primary_key=True)
    name: str = Field(min_length=3, max_length=100)
    email: EmailStr = SQLField(unique=True, index=True)
    password: str = Field(..., min_length=8, max_length=255)
    role: UserRole

class RegisterUser(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)

class PromoteUser(BaseModel):
    email: EmailStr

class LoginUser(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: UserRole

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse