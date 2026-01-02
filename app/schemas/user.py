from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
import re


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=30, pattern=r'^[a-zA-Z0-9_-]+$')
    full_name: Optional[str] = Field(None, max_length=100)
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        from app.core.security import validate_username
        if not validate_username(v):
            raise ValueError("Username must be 3-30 characters, alphanumeric with underscores or hyphens")
        return v.lower()  # Normalize to lowercase


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        from app.core.security import validate_password_strength
        is_valid, error_msg = validate_password_strength(v)
        if not is_valid:
            from pydantic import ValidationError
            raise ValidationError(error_msg)
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class User(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserInDB(User):
    hashed_password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None
