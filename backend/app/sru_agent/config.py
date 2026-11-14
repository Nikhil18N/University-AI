"""All settings in one place. Values come from environment variables or app settings."""
import os

try:
    from app.config import settings
    _default_keys = settings.get_gemini_api_keys()
    _default_key = _default_keys[0] if _default_keys else ""
    _default_redis = settings.REDIS_URL or ""
    _default_model = getattr(settings, "LLM_MODEL", "gemini-2.0-flash")
except Exception:
    _default_key = ""
    _default_redis = ""
    _default_model = "gemini-2.0-flash"

_raw_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or _default_key
GEMINI_API_KEY = _raw_key.split(",")[0].strip() if _raw_key else ""

# Use a valid Gemini model that supports function calling (avoid nonexistent names)
_raw_model = os.getenv("AGENT_MODEL") or _default_model
if _raw_model in ("gemini-2.5-flash", "gemini-3.1-flash-lite", ""):
    _raw_model = "gemini-2.0-flash"
AGENT_MODEL = _raw_model
AGENT_MAX_TOOL_ROUNDS = int(os.getenv("AGENT_MAX_TOOL_ROUNDS", "4"))
AGENT_MAX_MESSAGE_CHARS = int(os.getenv("AGENT_MAX_MESSAGE_CHARS", "1000"))
AGENT_RATE_LIMIT_PER_MIN = int(os.getenv("AGENT_RATE_LIMIT_PER_MIN", "20"))

REDIS_URL = os.getenv("REDIS_URL") or _default_redis

# Where leads are saved. Default = the backend's own existing endpoint.
LEADS_API_URL = os.getenv("LEADS_API_URL", "http://127.0.0.1:8000/api/v1/leads")

ADMISSION_YEAR = os.getenv("ADMISSION_YEAR", "2027-28")
APPLY_URL = os.getenv("APPLY_URL", "https://apply.sru.edu.in")
ADMISSIONS_PHONE = os.getenv("ADMISSIONS_PHONE", "0870-2818333")
ADMISSIONS_EMAIL = os.getenv("ADMISSIONS_EMAIL", "info@sru.edu.in")
# Digits only, with country code, e.g. 9198XXXXXXXX.
ADMISSIONS_WHATSAPP = os.getenv("ADMISSIONS_WHATSAPP", "918331003030")

