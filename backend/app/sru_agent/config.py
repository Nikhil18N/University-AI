"""All settings in one place. Values come from environment variables or app settings."""
import os

# Active model aliases for deprecated/unavailable Google Gemini models
MODEL_ALIASES = {
    "gemini-2.0-flash": "gemini-3.5-flash-lite",
    "gemini-2.0-flash-lite": "gemini-3.5-flash-lite",
    "gemini-2.5-flash": "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite": "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite": "gemini-3.5-flash-lite",
    "gemini-1.5-flash": "gemini-3.5-flash-lite",
    "gemini-1.5-pro": "gemini-3.5-flash-lite",
}

try:
    from app.config import settings
    _default_keys = settings.get_gemini_api_keys()
    _default_key = _default_keys[0] if _default_keys else ""
    _default_redis = settings.REDIS_URL or ""
    _default_model = getattr(settings, "LLM_MODEL", "gemini-3.5-flash-lite")
except Exception:
    _default_key = ""
    _default_redis = ""
    _default_model = "gemini-3.5-flash-lite"

_raw_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or _default_key
GEMINI_API_KEY = _raw_key.split(",")[0].strip() if _raw_key else ""


def _all_keys() -> list:
    """Every Gemini key configured (GEMINI_API_KEYS, GEMINI_API_KEY, GOOGLE_API_KEY), in order, no repeats.
    The agent rotates through them, so adding keys from separate Google projects adds capacity."""
    found = []
    try:
        found += list(_default_keys)
    except NameError:
        pass
    for var in ("GEMINI_API_KEYS", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        found += [k.strip() for k in (os.getenv(var) or "").split(",") if k.strip()]
    return list(dict.fromkeys(found))


GEMINI_API_KEYS = _all_keys()

# Map any legacy or deprecated model name to active production Gemini models
_raw_model = os.getenv("AGENT_MODEL") or _default_model
AGENT_MODEL = MODEL_ALIASES.get(_raw_model, _raw_model) or "gemini-3.5-flash-lite"
AGENT_MAX_TOOL_ROUNDS = int(os.getenv("AGENT_MAX_TOOL_ROUNDS", "4"))
AGENT_MAX_MESSAGE_CHARS = int(os.getenv("AGENT_MAX_MESSAGE_CHARS", "1000"))
AGENT_RATE_LIMIT_PER_MIN = int(os.getenv("AGENT_RATE_LIMIT_PER_MIN", "20"))
# Load handling: how many model calls may run at the same moment (the rest wait their turn),
# how long to wait before retrying a busy / rate-limited call, and how long one call may take.
AGENT_MAX_CONCURRENCY = int(os.getenv("AGENT_MAX_CONCURRENCY", "6"))
AGENT_RETRY_DELAYS = tuple(float(x) for x in os.getenv("AGENT_RETRY_DELAYS", "1.5,4,8").split(",") if x.strip())
AGENT_CALL_TIMEOUT = float(os.getenv("AGENT_CALL_TIMEOUT", "30"))
AGENT_KEY_COOLDOWN_SECONDS = float(os.getenv("AGENT_KEY_COOLDOWN_SECONDS", "45"))

REDIS_URL = os.getenv("REDIS_URL") or _default_redis

# Where leads are saved. Default = the backend's own existing endpoint.
LEADS_API_URL = os.getenv("LEADS_API_URL", "http://127.0.0.1:8000/api/v1/leads")

ADMISSION_YEAR = os.getenv("ADMISSION_YEAR", "2027-28")
APPLY_URL = os.getenv("APPLY_URL", "https://apply.sru.edu.in")
ADMISSIONS_PHONE = os.getenv("ADMISSIONS_PHONE", "0870-2818333")
ADMISSIONS_EMAIL = os.getenv("ADMISSIONS_EMAIL", "info@sru.edu.in")
# Digits only, with country code, e.g. 9198XXXXXXXX.
ADMISSIONS_WHATSAPP = os.getenv("ADMISSIONS_WHATSAPP", "918331003030")

