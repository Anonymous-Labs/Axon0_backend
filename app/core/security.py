"""
Security utilities for production deployment.
"""
import re
import html
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def sanitize_input(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize user input to prevent XSS and injection attacks.
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
    
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # HTML escape to prevent XSS
    text = html.escape(text)
    
    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
    
    # Limit length if specified
    if max_length and len(text) > max_length:
        text = text[:max_length]
        logger.warning("Input truncated", extra={"original_length": len(text), "max_length": max_length})
    
    return text.strip()


def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
    
    Returns:
        True if valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_username(username: str) -> bool:
    """
    Validate username format.
    
    Args:
        username: Username to validate
    
    Returns:
        True if valid, False otherwise
    """
    # Username: 3-30 chars, alphanumeric, underscore, hyphen
    pattern = r'^[a-zA-Z0-9_-]{3,30}$'
    return bool(re.match(pattern, username))


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password strength.
    
    Args:
        password: Password to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if len(password) > 128:
        return False, "Password must be less than 128 characters"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    # Check for common weak passwords
    common_passwords = ['password', '12345678', 'qwerty', 'abc123']
    if password.lower() in common_passwords:
        return False, "Password is too common. Please choose a stronger password"
    
    return True, ""


def sanitize_sql_like_pattern(pattern: str) -> str:
    """
    Sanitize SQL LIKE pattern to prevent injection.
    
    Args:
        pattern: Pattern string
    
    Returns:
        Sanitized pattern
    """
    # Escape SQL LIKE special characters
    pattern = pattern.replace('%', r'\%')
    pattern = pattern.replace('_', r'\_')
    return pattern


def rate_limit_key(identifier: str, endpoint: str) -> str:
    """
    Generate rate limit key.
    
    Args:
        identifier: Client identifier (IP or user ID)
        endpoint: API endpoint
    
    Returns:
        Rate limit key
    """
    # Sanitize to prevent key injection
    identifier = re.sub(r'[^a-zA-Z0-9_:.-]', '', identifier)
    endpoint = re.sub(r'[^a-zA-Z0-9_/]', '', endpoint)
    return f"rate_limit:{identifier}:{endpoint}"

