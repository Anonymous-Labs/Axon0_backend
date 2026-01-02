"""
Application configuration with validation and environment support.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Application Settings
    app_name: str = "Axon Memory System"
    app_version: str = "0.1.0"
    debug: bool = Field(default=False, description="Enable debug mode")
    environment: str = Field(
        default="development",
        description="Environment: development, staging, or production"
    )
    
    # Security - MUST be set via environment variables in production
    secret_key: str = Field(
        default="your-super-secret-key-change-this-in-production",
        description="Secret key for application security"
    )
    jwt_secret_key: str = Field(
        default="your-jwt-secret-key",
        description="Secret key for JWT token signing"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="JWT token expiration time in minutes"
    )

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///axon.db",
        description="Database connection URL"
    )
    database_pool_size: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Database connection pool size"
    )
    database_max_overflow: int = Field(
        default=20,
        ge=0,
        description="Maximum database connection pool overflow"
    )

    # Redis (for ARQ workers, caching, and rate limiting)
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL"
    )
    redis_ttl: int = Field(
        default=3600,
        ge=1,
        description="Default Redis TTL in seconds"
    )

    # Gemini API (for summarization and content restructuring)
    gemini_api_key: str = Field(
        default="",
        description="Google Gemini API key"
    )

    # Vector Database Settings (FAISS)
    faiss_index_path: str = Field(
        default="./data/faiss_indices",
        description="Path to store FAISS indices"
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence transformer model name"
    )
    embedding_dimension: int = Field(
        default=384,
        ge=128,
        description="Embedding vector dimension"
    )

    # Memory Processing Settings
    max_chunk_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Maximum characters per chunk"
    )
    chunk_overlap: int = Field(
        default=200,
        ge=0,
        description="Overlap between chunks in characters"
    )
    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Threshold for episodic clustering similarity"
    )

    # Server Settings
    host: str = Field(
        default="127.0.0.1",
        description="Server host address"
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Server port number"
    )

    # CORS Settings
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins"
    )

    # Worker Settings
    arq_workers: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Number of ARQ worker processes"
    )
    arq_max_jobs_per_worker: int = Field(
        default=10,
        ge=1,
        description="Maximum jobs per ARQ worker"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v
    
    @field_validator("secret_key", "jwt_secret_key")
    @classmethod
    def validate_secrets(cls, v: str, info) -> str:
        """Validate that secrets are set in production."""
        # Only validate in production
        # This will be checked during initialization
        return v
    
    def validate_production_secrets(self) -> None:
        """
        Validate that required secrets are properly set in production.
        
        Raises:
            ValueError: If secrets are not properly configured
        """
        if self.environment == "production":
            default_secret = "your-super-secret-key-change-this-in-production"
            default_jwt = "your-jwt-secret-key"
            
            if not self.secret_key or self.secret_key == default_secret:
                raise ValueError(
                    "SECRET_KEY must be set to a secure value in production. "
                    "Do not use the default value."
                )
            
            if not self.jwt_secret_key or self.jwt_secret_key == default_jwt:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a secure value in production. "
                    "Do not use the default value."
                )
            
            if len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters long in production"
                )
            
            if len(self.jwt_secret_key) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be at least 32 characters long in production"
                )
    
    def ensure_directories(self) -> None:
        """Ensure required directories exist."""
        os.makedirs(self.faiss_index_path, exist_ok=True)


# Create settings instance
settings = Settings()

# Validate production secrets if in production
if settings.environment == "production":
    settings.validate_production_secrets()

# Ensure required directories exist
settings.ensure_directories()
