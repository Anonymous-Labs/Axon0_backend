import secrets
import string
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, update

from app.models.memory import APIKey
from app.schemas.memory import APIKeyCreate, APIKeyList


class APIKeyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def generate_api_key(length: int = 32) -> str:
        """Generate a secure random API key."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    async def create_api_key(self, key_data: APIKeyCreate, user_id: int) -> APIKey:
        """Create a new API key for a user."""
        api_key_value = self.generate_api_key()

        # Check if key name already exists for this user
        existing = await self.db.execute(
            select(APIKey).where(
                and_(APIKey.user_id == user_id, APIKey.name == key_data.name)
            )
        )
        if existing.scalars().first():
            raise ValueError("API key with this name already exists")

        db_api_key = APIKey(
            user_id=user_id,
            key=api_key_value,
            name=key_data.name,
            description=key_data.description,
            permissions=key_data.permissions,
            expires_at=key_data.expires_at,
        )

        self.db.add(db_api_key)
        await self.db.commit()
        await self.db.refresh(db_api_key)
        return db_api_key

    async def get_user_api_keys(self, user_id: int) -> List[APIKeyList]:
        """Get all API keys for a user (without showing the actual key)."""
        result = await self.db.execute(
            select(APIKey).where(APIKey.user_id == user_id)
        )
        api_keys = result.scalars().all()

        # Convert to APIKeyList (without the actual key)
        return [
            APIKeyList(
                id=key.id,
                name=key.name,
                description=key.description,
                permissions=key.permissions,
                is_active=key.is_active,
                expires_at=key.expires_at,
                created_at=key.created_at,
                last_used_at=key.last_used_at,
                usage_count=key.usage_count,
            )
            for key in api_keys
        ]

    async def get_api_key_by_value(self, api_key_value: str) -> Optional[APIKey]:
        """Get API key by its value (for authentication)."""
        result = await self.db.execute(
            select(APIKey).where(APIKey.key == api_key_value)
        )
        api_key = result.scalars().first()

        if api_key and api_key.is_active:
            # Check if expired
            if api_key.expires_at and api_key.expires_at < datetime.utcnow():
                api_key.is_active = False
                await self.db.commit()
                return None

            # Update usage statistics
            api_key.last_used_at = datetime.utcnow()
            api_key.usage_count += 1
            await self.db.commit()

            return api_key

        return None

    async def update_api_key(self, key_id: int, user_id: int, updates: dict) -> Optional[APIKey]:
        """Update an API key."""
        result = await self.db.execute(
            select(APIKey).where(
                and_(APIKey.id == key_id, APIKey.user_id == user_id)
            )
        )
        api_key = result.scalars().first()

        if not api_key:
            return None

        # Update allowed fields
        allowed_updates = ['name', 'description', 'permissions', 'is_active', 'expires_at']
        for field in allowed_updates:
            if field in updates:
                setattr(api_key, field, updates[field])

        api_key.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(api_key)
        return api_key

    async def delete_api_key(self, key_id: int, user_id: int) -> bool:
        """Delete an API key."""
        result = await self.db.execute(
            select(APIKey).where(
                and_(APIKey.id == key_id, APIKey.user_id == user_id)
            )
        )
        api_key = result.scalars().first()

        if not api_key:
            return False

        await self.db.delete(api_key)
        await self.db.commit()
        return True

    async def validate_permissions(self, api_key: APIKey, required_permissions: List[str]) -> bool:
        """Check if API key has required permissions."""
        if not api_key.is_active:
            return False

        # Check if key has all required permissions
        key_permissions = set(api_key.permissions or [])
        required_perms = set(required_permissions)

        return required_perms.issubset(key_permissions)


# Dependency function for getting API key service
async def get_api_key_service(db: AsyncSession) -> APIKeyService:
    return APIKeyService(db)
