from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Application Settings
    app_name: str = "Axon Memory System"
    app_version: str = "0.1.0"
    debug: bool = True
    secret_key: str = "your-super-secret-key-change-this-in-production"

    # Database
    database_url: str = "sqlite+aiosqlite:///axon.db"

    # Redis (for ARQ workers and caching)
    redis_url: str = "redis://localhost:6379"

    # Gemini API (for summarization and content restructuring)
    gemini_api_key: str = ""

    # Vector Database Settings (FAISS)
    faiss_index_path: str = "./data/faiss_indices"
    embedding_model: str = "all-MiniLM-L6-v2"  # Sentence transformer model
    embedding_dimension: int = 384  # Dimension for all-MiniLM-L6-v2

    # Memory Processing Settings
    max_chunk_size: int = 1000  # Maximum characters per chunk
    chunk_overlap: int = 200  # Overlap between chunks
    similarity_threshold: float = 0.7  # Threshold for episodic clustering

    # JWT Settings
    jwt_secret_key: str = "your-jwt-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # Server Settings
    host: str = "127.0.0.1"
    port: int = 8000

    # CORS Settings
    allowed_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Worker Settings
    arq_workers: int = 4
    arq_max_jobs_per_worker: int = 10

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
