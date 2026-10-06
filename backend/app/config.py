"""Application configuration loaded from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All settings are loaded from env vars or a .env file."""

    # ---- LLM ----
    LLM_PROVIDER: str = "ollama"
    LLM_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "llama3.2"
    LLM_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""

    # ---- Embedding ----
    EMBEDDING_PROVIDER: str = "ollama"
    EMBEDDING_MODEL: str = "nomic-embed-text"

    # ---- Database ----
    DATABASE_URL: str = "postgresql+asyncpg://university_ai:university_ai_dev@localhost:5433/university_ai"

    # ---- Redis ----
    REDIS_URL: str = "redis://localhost:6379/0"

    # ---- ChromaDB ----
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    RAG_MAX_DISTANCE: float = 0.5

    # ---- Admin ----
    ADMIN_API_KEY: str = "change-me-in-production"

    # ---- App ----
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:5173"

    # ---- Paths ----
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
    PROMPTS_DIR: Path = PROJECT_ROOT / "prompts"
    UPLOAD_DIR: Path = PROJECT_ROOT / "uploads"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
