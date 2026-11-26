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
# Conversation memory: a student who comes back after this many minutes without a message is asked whether
# to continue the previous conversation or start a new one. Sooner than that (a refresh, a short break) the
# conversation simply continues. The browser reads this value from /recovery-context (one source of truth).
RECOVERY_RESUME_AFTER_MINUTES = int(os.getenv("RECOVERY_RESUME_AFTER_MINUTES", "30"))
# Load handling: how many model calls may run at the same moment (the rest wait their turn),
# how long to wait before retrying a busy / rate-limited call, and how long one call may take.
AGENT_MAX_CONCURRENCY = int(os.getenv("AGENT_MAX_CONCURRENCY", "6"))
# Shorter waits than before (1.5, 4, 8 s): with several keys the next key is tried at once anyway,
# and a student would rather get the quick fee-table answer than wait 13 seconds.
AGENT_RETRY_DELAYS = tuple(float(x) for x in os.getenv("AGENT_RETRY_DELAYS", "1,2.5").split(",") if x.strip())
AGENT_CALL_TIMEOUT = float(os.getenv("AGENT_CALL_TIMEOUT", "25"))
AGENT_TOTAL_TIMEOUT = float(os.getenv("AGENT_TOTAL_TIMEOUT", "45"))
# Thinking makes Gemini 3 models slower. MINIMAL (or LOW where a model has no MINIMAL) is right for
# an admissions assistant whose facts come from tools; DEFAULT leaves the model's own setting.
AGENT_THINKING_LEVEL = os.getenv("AGENT_THINKING_LEVEL", "MINIMAL")
# Send the answer to the browser while Gemini is still writing it (first words ~1-2 s sooner).
AGENT_STREAM = os.getenv("AGENT_STREAM", "true").strip().lower() in ("1", "true", "yes", "on")
AGENT_EXPLICIT_CACHE = os.getenv("AGENT_EXPLICIT_CACHE", "true").strip().lower() in ("1", "true", "yes", "on")
AGENT_KEY_COOLDOWN_SECONDS = float(os.getenv("AGENT_KEY_COOLDOWN_SECONDS", "45"))
# A key that hit its PER-DAY limit is rested this long before it is tried again:
AGENT_DAILY_LIMIT_COOLDOWN = float(os.getenv("AGENT_DAILY_LIMIT_COOLDOWN", "3600"))
# The same first question from different students (for example a suggestion button) is answered
# from a saved copy for this many seconds instead of calling the model again. 0 switches it off.
# No longer used: the agent does not cache answers (v4.10.0). Kept so older settings and tests still load.
AGENT_ANSWER_CACHE_SECONDS = int(os.getenv("AGENT_ANSWER_CACHE_SECONDS", "3600"))

REDIS_URL = os.getenv("REDIS_URL") or _default_redis

def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")

# Speed (see memory.py): keep each student's profile / chat context in this server's memory and
# write Redis and the database in the background. Right for ONE server process; set
# AGENT_LOCAL_CACHE=false if you run several (uvicorn --workers N or several instances).
AGENT_LOCAL_CACHE = _flag("AGENT_LOCAL_CACHE", "true")
AGENT_BACKGROUND_WRITES = _flag("AGENT_BACKGROUND_WRITES", "true")

# Where leads are saved. Default = the backend's own existing endpoint.
LEADS_API_URL = os.getenv("LEADS_API_URL", "http://127.0.0.1:8000/api/v1/leads")

ADMISSION_YEAR = os.getenv("ADMISSION_YEAR", "2027-28")
APPLY_URL = os.getenv("APPLY_URL", "https://apply.sru.edu.in")
ADMISSIONS_PHONE = os.getenv("ADMISSIONS_PHONE", "833 100 3030")
ADMISSIONS_EMAIL = os.getenv("ADMISSIONS_EMAIL", "info@sru.edu.in")
# Digits only, with country code, e.g. 9198XXXXXXXX.
ADMISSIONS_WHATSAPP = os.getenv("ADMISSIONS_WHATSAPP", "918331003030")
# Campus visits are arranged by the admissions team (sru.edu.in/visit-us, checked 17 Nov 2026).
# SRU Buddy never books or confirms a visit; it shares these contacts or passes on a callback request.
CAMPUS_VISIT_PHONE = os.getenv("CAMPUS_VISIT_PHONE", "833 100 4040")
CAMPUS_VISIT_WHATSAPP = os.getenv("CAMPUS_VISIT_WHATSAPP", "918331004040")
CAMPUS_VISIT_URL = os.getenv("CAMPUS_VISIT_URL", "https://sru.edu.in/visit-us")
CAMPUS_ADDRESS = os.getenv("CAMPUS_ADDRESS", "SR University, Ananthasagar, Hasanparthy, Warangal Urban 506371, Telangana")
FEE_PORTAL_URL = os.getenv("FEE_PORTAL_URL", "https://sru.edu.in/fee-scholarship/")
FACULTY_URL = "https://sru.edu.in/faculty/"

