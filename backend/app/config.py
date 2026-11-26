"""Application configuration loaded from environment variables."""

from pathlib import Path
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseModel as BaseSettings


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
    AUTO_CREATE_SCHEMA: bool = False
    # Apply the Alembic migrations when the API starts (hosts without a shell, e.g. Render free tier).
    RUN_MIGRATIONS_ON_START: bool = True

    # ---- Redis ----
    REDIS_URL: str = "redis://localhost:6379/0"
    RAG_CACHE_VERSION: str = "1"

    # ---- ChromaDB ----
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_PERSIST_DIR: str | None = "./chroma_data"
    RAG_MAX_DISTANCE: float = 0.60
    RAG_TOP_K: int = 5
    RAG_RERANK: bool = False

    # ---- Admin ----
    # The "Early Bird: 50% off the application fee (pay ₹550)" advertisement card. It is NOT on
    # the official 2027-28 fee card, so it stays hidden until the Admissions Office confirms the
    # offer. Set SHOW_EARLY_BIRD_OFFER=true in the server environment to show it.
    SHOW_EARLY_BIRD_OFFER: bool = False
    ADMIN_API_KEY: str = "change-me-in-production"

    # ---- App ----
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:5173"
    # Other sites allowed to call this API (regular expression). The default allows local
    # development, this project's Vercel deployments (university-ai-companion.vercel.app and its
    # preview URLs) and sru.edu.in with its subdomains. It no longer allows every *.vercel.app site.
    CORS_ORIGIN_REGEX: str = (
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        r"|^https://university-ai-companion(-[a-z0-9-]+)?\.vercel\.app$"
        r"|^https://([a-zA-Z0-9-]+\.)*sru\.edu\.in$"
    )

    # ---- Security (see security/DEPLOYMENT_SECURITY.md) ----
    # Proxies in front of the server that append to X-Forwarded-For (Render: 1). 0 = no proxy.
    TRUSTED_PROXY_HOPS: int = 1
    # A header the platform sets to the real client IP (e.g. "cf-connecting-ip"); empty = not used.
    CLIENT_IP_HEADER: str = ""
    # AI-backed chat turns: per IP per minute, per IP per day, and for the whole server per day (0 = off).
    AI_IP_RATE_LIMIT_PER_MIN: int = 40
    AI_IP_DAILY_LIMIT: int = 600
    AI_DAILY_TURN_BUDGET: int = 20000
    # Largest request body accepted (bytes): API requests, and admin document uploads.
    MAX_REQUEST_BYTES: int = 256 * 1024
    MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024

    # ---- Paths ----
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
    BACKEND_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = (
        (BACKEND_DIR / "data")
        if (BACKEND_DIR / "data").exists()
        else (PROJECT_ROOT / "data")
    )
    PROMPTS_DIR: Path = (
        (BACKEND_DIR / "prompts")
        if (BACKEND_DIR / "prompts").exists()
        else (PROJECT_ROOT / "prompts")
    )
    UPLOAD_DIR: Path = (
        PROJECT_ROOT / "uploads"
        if (PROJECT_ROOT / "uploads").exists()
        else (BACKEND_DIR / "uploads")
    )

    model_config = {
        "env_file": [
            ".env",
            str(Path(__file__).resolve().parent.parent / ".env"),
            str(Path(__file__).resolve().parent.parent.parent / ".env"),
        ],
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def admin_key_is_default(self) -> bool:
        """True while ADMIN_API_KEY is missing or still the placeholder shipped in the source code."""
        return (self.ADMIN_API_KEY or "").strip() in ("", "change-me-in-production")

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
