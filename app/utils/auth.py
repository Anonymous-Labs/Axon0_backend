from datetime import datetime, timedelta
from typing import Optional
import hashlib
import secrets
from jose import JWTError, jwt
from app.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash using PBKDF2."""
    try:
        # Extract salt and hash from stored password
        salt_hex, stored_hash = hashed_password.split('$', 1)
        salt = bytes.fromhex(salt_hex)

        # Hash the input password with the same salt
        input_hash = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt,
            100000  # iterations
        ).hex()

        return secrets.compare_digest(input_hash, stored_hash)
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    """Hash a password for storing using PBKDF2."""
    # Generate a random salt
    salt = secrets.token_bytes(16)

    # Hash the password
    hash_obj = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000  # iterations
    )

    # Store as salt$hash format
    return f"{salt.hex()}${hash_obj.hex()}"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def verify_token(token: str) -> Optional[str]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None
