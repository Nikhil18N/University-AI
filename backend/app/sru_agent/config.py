"""All settings in one place. Values come from environment variables or app settings."""
import os

try:
    from app.config import settings
    _default_key = settings.get_gemini_api_keys()[0] if settings.get_gemini_api_keys() else ""
    _default_redis = settings.REDIS_URL or ""
except Exception:
    _default_key = ""
    _default_redis = ""

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or _default_key
# Use a current Gemini model that supports function calling.
AGENT_MODEL = os.getenv("AGENT_MODEL", "gemini-2.5-flash")
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

