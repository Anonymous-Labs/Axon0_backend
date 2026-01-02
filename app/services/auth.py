from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from app.models.user import User
from app.schemas.user import UserCreate, UserInDB, TokenData
from app.utils.auth import get_password_hash, verify_password, verify_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user with username/email and password."""
        # Try to find user by username or email
        result = await self.db.execute(
            select(User).where(
                (User.username == username) | (User.email == username)
            )
        )
        user = result.scalars().first()

        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def get_current_user(self, token: str = None) -> User:
        """Get the current authenticated user from JWT token."""
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )

        username = verify_token(token)
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        result = await self.db.execute(select(User).where(User.username == username))
        user = result.scalars().first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    async def create_user(self, user_data: UserCreate) -> User:
        """
        Create a new user with validation and security checks.
        
        Args:
            user_data: User creation data
        
        Returns:
            Created user
        
        Raises:
            HTTPException: If user creation fails
        """
        # Validate password strength
        from app.core.security import validate_password_strength, sanitize_input
        is_valid, error_msg = validate_password_strength(user_data.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Sanitize inputs
        sanitized_email = sanitize_input(user_data.email.lower().strip(), max_length=255)
        sanitized_username = sanitize_input(user_data.username.lower().strip(), max_length=30)
        sanitized_full_name = sanitize_input(user_data.full_name, max_length=100) if user_data.full_name else None
        
        # Check if user already exists
        result = await self.db.execute(
            select(User).where(
                (User.email == sanitized_email) | (User.username == sanitized_username)
            )
        )
        existing_user = result.scalars().first()
        if existing_user:
            # Don't reveal which field is duplicate for security
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email or username already exists"
            )

        # Create new user
        hashed_password = get_password_hash(user_data.password)
        db_user = User(
            email=sanitized_email,
            username=sanitized_username,
            full_name=sanitized_full_name,
            hashed_password=hashed_password,
        )

        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()


# Dependency function for getting auth service
async def get_auth_service(db: AsyncSession) -> AuthService:
    return AuthService(db)
