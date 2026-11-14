"""Application configuration loaded from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All settings are loaded from env vars or a .env file."""

    # ---- LLM ----
    LLM_PROVIDER: str = "gemini"
    LLM_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "gemini-3.1-flash-lite"
    LLM_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEYS: str = ""  # Comma-separated list of Gemini API keys for pooling/rotation
    GOOGLE_API_KEY: str | None = None
    OPENROUTER_API_KEY: str = ""

    # ---- Embedding ----
    EMBEDDING_PROVIDER: str = "gemini"
    EMBEDDING_MODEL: str = "gemini-embedding-001"

    # ---- Database ----
    DATABASE_URL: str = "postgresql+asyncpg://university_ai:university_ai_dev@localhost:5433/university_ai"

    # ---- Redis ----
    REDIS_URL: str = "redis://localhost:6379/0"

    # ---- ChromaDB ----
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_PERSIST_DIR: str | None = "./chroma_data"
    RAG_MAX_DISTANCE: float = 0.60
    RAG_TOP_K: int = 5
    RAG_RERANK: bool = False

    # ---- Admin ----
    ADMIN_API_KEY: str = "change-me-in-production"

    # ---- App ----
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:5173"

    # ---- Paths ----
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
    PROMPTS_DIR: Path = (
        PROJECT_ROOT / "prompts"
        if (PROJECT_ROOT / "prompts").exists()
        else (Path(__file__).resolve().parent.parent / "prompts")
    )
    UPLOAD_DIR: Path = (
        PROJECT_ROOT / "uploads"
        if (PROJECT_ROOT / "uploads").exists()
        else (Path(__file__).resolve().parent.parent / "uploads")
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def get_gemini_api_keys(self) -> list[str]:
        """Return a deduplicated list of Gemini API keys configured from GEMINI_API_KEYS, GEMINI_API_KEY, or GOOGLE_API_KEY.
        Handles comma-separated strings in any key variable so users can paste lists into GEMINI_API_KEY or GEMINI_API_KEYS.
        """
        all_keys: list[str] = []
        candidates = [self.GEMINI_API_KEYS, self.GEMINI_API_KEY, self.GOOGLE_API_KEY]
        if self.LLM_PROVIDER.lower() == "gemini" and self.LLM_API_KEY:
            candidates.append(self.LLM_API_KEY)

        for raw in candidates:
            if raw:
                all_keys.extend(k.strip() for k in str(raw).split(",") if k.strip())

        return list(dict.fromkeys(all_keys))


settings = Settings()
