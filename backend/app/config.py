"""Application configuration loaded from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All settings are loaded from env vars or a .env file."""

    # ---- LLM ----
    LLM_PROVIDER: str = "gemini"
    LLM_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "gemini-3.5-flash-lite"
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
    RESPONSE_CACHE_ENABLED: bool = True

    # ---- ChromaDB ----
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_PERSIST_DIR: str | None = "./chroma_data"
    CHROMA_FACTS_COLLECTION: str = "sru_facts"
    CHROMA_HIGHLIGHTS_COLLECTION: str = "sru_highlights"
    RAG_MAX_DISTANCE: float = 0.60
    RAG_TOP_K: int = 8
    RAG_RERANK: bool = True
    HYBRID_RETRIEVAL_ENABLED: bool = True

    # ---- Admin ----
    ADMIN_API_KEY: str = "change-me-in-production"

    # ---- App ----
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:5173"
    SHOW_SOURCES: bool = False
    CONVERSATION_RETENTION_DAYS: int = 90

    # ---- University Contacts & Helplines (T7) ----
    ADMISSIONS_PHONE: str = "0870-2818333"
    ADMISSIONS_PHONE_ALT: str = "0870-2818311"
    ADMISSIONS_EMAIL: str = "info@sru.edu.in"
    HELPDESK_EMAIL: str = "helpdesk@sru.edu.in"
    ADMISSIONS_PORTAL_URL: str = "https://apply.sru.edu.in"
    CAMPUS_LOCATION: str = "Ananthasagar, Hasanparthy, Warangal, Telangana 506371"

    CRISIS_HELPLINES: list[dict[str, str]] = [
        {
            "name": "Tele-MANAS",
            "number": "14416",
            "alt_number": "1800-891-4416",
            "hours": "24/7",
            "languages": "English, Telugu, Hindi, and 20+ regional languages",
        },
        {
            "name": "AASRA",
            "number": "+91-9820466726",
            "alt_number": "9820466726",
            "hours": "24/7",
            "languages": "English, Hindi",
        },
        {
            "name": "Kiran Mental Health Helpline",
            "number": "1800-599-0019",
            "alt_number": "18005990019",
            "hours": "24/7",
            "languages": "English, Hindi, Telugu, and 10+ languages",
        },
    ]

    # ---- Paths ----
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
    PROMPTS_DIR: Path = PROJECT_ROOT / "prompts"
    UPLOAD_DIR: Path = PROJECT_ROOT / "uploads"

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
