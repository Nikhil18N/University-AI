"""Chat behaviour settings the admissions team can switch in the admin panel (v4.12.0), without code changes.

Stored in the existing `user_memories` table under a reserved system session ("system:app-settings", which a
student session ID can never be: those match SESSION_ID_PATTERN, no colon), one row per setting with the key
prefix "setting.". No new table, so no migration is needed and a change works on the live server at once.

Reads are served from an in-process cache refreshed at most every CACHE_SECONDS (the agent calls refresh()
at the start of each turn); an update is written to the database and applied to the cache immediately. If the
database cannot be reached, the last known values (or the defaults) are used, so the chat never breaks.
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

log = logging.getLogger(__name__)

SYSTEM_SESSION = "system:app-settings"
PREFIX = "setting."
CACHE_SECONDS = 20
# memory_value is VARCHAR(255): a longer value (the Quick Start tiles) is saved in numbered pieces
# ("setting.welcome_tiles#0", "#1", ...) under a small index row, and put back together on load. No migration.
CHUNK = 240

WELCOME_ICONS = ("calculator", "graduation-cap", "briefcase", "heart", "award", "building", "home", "map-pin",
                 "phone", "book", "wallet", "send")


class WelcomeTile(BaseModel):
    """One Quick Start tile under the opening welcome message (Admin -> Agent -> Quick Start tiles)."""

    id: str = Field(..., pattern=r"^[a-z0-9_-]{1,24}$")
    title: str = Field(..., min_length=1, max_length=32)
    badge: str = Field("", max_length=16, description="Short highlight on the tile (verified facts only)")
    icon: Literal[WELCOME_ICONS] = "building"  # type: ignore[valid-type]
    prompt: str = Field(..., min_length=1, max_length=120, description="The message sent when the tile is tapped")
    subtitle: str = Field("", max_length=48, description="Shown as the tile's tooltip")
    enabled: bool = True

    @field_validator("title", "badge", "prompt", "subtitle")
    @classmethod
    def _plain(cls, v: str) -> str:
        v = re.sub(r"\s+", " ", v or "").strip()
        if re.search(r"[<>]", v):
            raise ValueError("no < or > characters")
        return v


# Verified badges only: fee card slabs (up to 40%), NIRF 2025 Engineering #91, THE Research Quality #6 in India,
# placements page (highest 51 LPA), special concessions on the fee card (15,000 to 50,000 a year).
DEFAULT_WELCOME_TILES = [
    {"id": "calculate_scholarship", "title": "Calculate My Scholarship", "badge": "Up to 40% off", "icon": "calculator",
     "prompt": "Calculate my scholarship", "subtitle": "Instant fee estimate in a few steps"},
    {"id": "explore_programs", "title": "Explore Programmes", "badge": "NIRF #91", "icon": "graduation-cap",
     "prompt": "Explore programs offered at SR University", "subtitle": "B.Tech, MBA, Agriculture & more"},
    {"id": "placements", "title": "Placements & Careers", "badge": "₹51 LPA", "icon": "briefcase",
     "prompt": "Tell me about placements at SRU", "subtitle": "150+ recruiters, 1,300+ offers"},
    {"id": "special_consideration", "title": "Special Consideration", "badge": "₹15K–₹50K/yr", "icon": "heart",
     "prompt": "Special consideration", "subtitle": "Concessions you may qualify for"},
    {"id": "why_sru", "title": "Why Choose SRU?", "badge": "#6 Research", "icon": "award",
     "prompt": "Why should I choose SR University?", "subtitle": "Rankings, research and campus life"},
]


# ---- v4.14.0: event highlights and the official YouTube videos, both edited in Admin -> Campus media ---------
VIDEO_TOPICS = ("Campus Life & Fests", "Hostels & Living", "Sports & Activities", "Campus Tour & Infrastructure",
                "Placements & Careers", "CS, AI & Technology", "MBA & Business", "School of Agriculture",
                "Startups & Innovation (SRiX)", "International Programs", "International Student Experience",
                "Testimonials & Reviews")
_YOUTUBE_ID = r"^[A-Za-z0-9_-]{11}$"


def _plain_text(v: str) -> str:
    v = re.sub(r"\s+", " ", v or "").strip()
    if re.search(r"[<>]", v):
        raise ValueError("no < or > characters")
    return v


class EventHighlight(BaseModel):
    """One event in the chat's event highlights (a photo card). Verified facts only."""

    id: str = Field(..., pattern=r"^[a-z0-9_-]{1,32}$")
    title: str = Field(..., min_length=1, max_length=60)
    when: str = Field("", max_length=60, description="e.g. '26 January 2027' or 'Every year'")
    summary: str = Field("", max_length=220, description="One or two sentences, shown on the card and in answers")
    image_url: str = Field("", max_length=400, description="An https:// image link, e.g. from sru.edu.in")
    video_id: str = Field("", description="Optional: the YouTube video id of this event (11 characters)")
    keywords: str = Field("", max_length=200, description="Other names students use, comma separated")
    enabled: bool = True

    @field_validator("title", "when", "summary", "keywords")
    @classmethod
    def _plain(cls, v: str) -> str:
        return _plain_text(v)

    @field_validator("image_url")
    @classmethod
    def _https(cls, v: str) -> str:
        return _image_source(v)

    @field_validator("video_id")
    @classmethod
    def _video(cls, v: str) -> str:
        v = youtube_id(v) if v else ""
        if v and not re.fullmatch(_YOUTUBE_ID, v):
            raise ValueError("use a YouTube link or its 11-character video id")
        return v


def youtube_id(value: str) -> str:
    """The 11-character id from a YouTube link (watch, youtu.be, shorts, embed) or the id itself."""
    value = (value or "").strip()
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})", value)
    return m.group(1) if m else value


class AddedVideo(BaseModel):
    """An official SRU YouTube video added in the admin panel (the built-in list is in app/data)."""

    id: str = Field(..., description="YouTube link or video id")
    title: str = Field(..., min_length=1, max_length=140)
    category: Literal[VIDEO_TOPICS] = "Campus Life & Fests"  # type: ignore[valid-type]
    type: Literal["video", "short"] = "video"
    keywords: str = Field("", max_length=200)

    @field_validator("id", mode="before")
    @classmethod
    def _id(cls, v: str) -> str:
        v = youtube_id(str(v or ""))
        if not re.fullmatch(_YOUTUBE_ID, v):
            raise ValueError("use a YouTube link or its 11-character video id")
        return v

    @field_validator("title", "keywords")
    @classmethod
    def _plain(cls, v: str) -> str:
        return _plain_text(v)


class VideoSettings(BaseModel):
    """Changes to the official video list: videos hidden, the topic a video is shown for, videos added."""

    hidden: list[str] = Field(default_factory=list, max_length=300)
    topics: dict[str, Literal[VIDEO_TOPICS]] = Field(default_factory=dict)  # type: ignore[valid-type]
    added: list[AddedVideo] = Field(default_factory=list, max_length=60)

    @field_validator("hidden")
    @classmethod
    def _ids(cls, v: list[str]) -> list[str]:
        ids = list(dict.fromkeys(youtube_id(x) for x in v))
        if any(not re.fullmatch(_YOUTUBE_ID, x) for x in ids):
            raise ValueError("hidden videos are YouTube ids")
        return ids

    @field_validator("topics")
    @classmethod
    def _topic_ids(cls, v: dict) -> dict:
        if len(v) > 300 or any(not re.fullmatch(_YOUTUBE_ID, k) for k in v):
            raise ValueError("topics are keyed by YouTube id")
        return v

    @field_validator("added")
    @classmethod
    def _unique(cls, v: list) -> list:
        ids = [x.id for x in v]
        if len(set(ids)) != len(ids):
            raise ValueError("each added video only once")
        return v


_IMG = "https://sru.edu.in/wp-content/uploads"
_THUMB = "https://i.ytimg.com/vi/{}/hqdefault.jpg"
# From SR University's official sources only (sru.edu.in Events / Campus Life pages, the admissions presentation
# of 30 Oct 2026, the official YouTube channel), as approved by the admissions team on 24 Nov 2026.
DEFAULT_EVENT_HIGHLIGHTS = [
    {"id": "sparkrill", "title": "Sparkrill – Annual Cultural Fest", "when": "26 January 2027 (Sparkill '27)",
     "summary": "SRU's annual day and biggest cultural festival: performances, live music by guest artists and the "
                "fashion ramp walk.",
     "image_url": f"{_IMG}/2026/09/Upcoming_Events_7.webp", "video_id": "kFkaSToBX-A",
     "keywords": "sparkrill, sparkill, spark rill, spark ill, annual day, annual fest, cultural fest"},
    {"id": "lumina", "title": "Lumina – Hostel Night", "when": "Every year · Girls' and Boys' nights",
     "summary": "The hostellers' own annual celebration (Hostel Night, also called Hostel Hawa): music, dance and "
                "memories with friends.",
     "image_url": _THUMB.format("ITwoDHleH8g"), "video_id": "ITwoDHleH8g",
     "keywords": "lumina, hostel night, hostel nights, hostel hawa, hostel event, hostel fest, hostel party"},
    {"id": "navadhara", "title": "Navadhara – Talent & Culture", "when": "6 November 2026",
     "summary": "A celebration of talent and culture held with Bathukamma, Telangana's festival of flowers.",
     "image_url": f"{_IMG}/2025/06/Upcoming_Events_3.webp", "video_id": "mF_4tWXedd4",
     "keywords": "navadhara, nava dhara, navadara, bathukamma, batukamma"},
    {"id": "pragathi", "title": "PRAGATHI – Project Expo", "when": "9 October 2026 (PRAGATHI 2.0)",
     "summary": "The national project exhibition where students show what they have built; featured on ETV News.",
     "image_url": f"{_IMG}/2026/09/Upcoming_Events_1.webp", "video_id": "-9F-OFTDtuA",
     "keywords": "pragathi, pragati, project expo, projects expo, yantra, project exhibition, innovation fest"},
    {"id": "swagatham", "title": "Swagatham – Freshers' Welcome", "when": "16 October 2026",
     "summary": "The welcome festival for new students, with celebrations that start campus life.",
     "image_url": f"{_IMG}/2026/09/Upcoming_Events_6.webp", "video_id": "MWekBu0VLas",
     "keywords": "swagatham, swagatam, swagath, freshers, fresher, freshers party, welcome party"},
    {"id": "sports_day", "title": "Annual Sports Day", "when": "Every year (24th edition in 2026)",
     "summary": "A day of sports across the campus, alongside the annual inter-university tournaments.",
     "image_url": f"{_IMG}/2026/09/sportandfitness.webp", "video_id": "sf2jDM21EN4",
     "keywords": "sports day, sports meet, annual sports, tournament, tournaments"},
    {"id": "hackathon", "title": "Hackathons", "when": "Through the year",
     "summary": "Overnight programming hackathons (8 PM to 8 AM) by the School of CS & AI and the Hackathon Club.",
     "image_url": _THUMB.format("oFx9HUKmMc0"), "video_id": "oFx9HUKmMc0",
     "keywords": "hackathon, hackathons, coding contest, coding competition, technical fest, tech fest"},
    {"id": "campus_celebrations", "title": "Auto Expo, Campus Joy & Traditional Days", "when": "Through the year",
     "summary": "Auto Expo, cultural evenings and traditional celebrations from the Campus Life gallery.",
     "image_url": f"{_IMG}/2026/10/Campus_Life_auto_Expo-scaled.webp", "video_id": "",
     "keywords": "auto expo, traditional day, traditional activities, campus joy"},
    {"id": "more_events", "title": "Orientation, SRU-MUN, Alumni Meet & Convocation", "when": "Every year",
     "summary": "Orientation Day for new students, SRU-MUN (Model United Nations), the Alumni Meet and Convocation "
                "Day: part of 50+ events a year.",
     "image_url": f"{_IMG}/2026/10/campus-auditorium4-scaled.webp", "video_id": "",
     "keywords": "orientation day, orientation, induction, sru-mun, sru mun, model united nations, alumni meet, convocation, graduation day"},
]


class ChatAd(BaseModel):
    """A small ad at the bottom of the chat (Admin -> Campus media -> Ads): a cover image, a highlight line, a tag
    and a button. Verified offers only; links open in a new tab."""

    id: str = Field(..., pattern=r"^[a-z0-9_-]{1,32}$")
    title: str = Field(..., min_length=1, max_length=70, description="The highlight, e.g. 'Admissions open 2027-28'")
    subtitle: str = Field("", max_length=90, description="One short line under the highlight")
    tag: str = Field("", max_length=18, description="A small label, e.g. 'New' or 'Apply now'")
    image_url: str = Field("", max_length=400, description="Cover image: an https:// link")
    cta_text: str = Field("Know more", max_length=24, description="The button")
    link_url: str = Field("", max_length=400, description="Where the button goes: an https:// link")
    enabled: bool = True

    @field_validator("title", "subtitle", "tag", "cta_text")
    @classmethod
    def _plain(cls, v: str) -> str:
        return _plain_text(v)

    @field_validator("link_url")
    @classmethod
    def _https(cls, v: str) -> str:
        v = (v or "").strip()
        if v and not re.fullmatch(r"https://[^\s\"'<>]+", v):
            raise ValueError("links must start with https://")
        return v

    @field_validator("image_url")
    @classmethod
    def _image(cls, v: str) -> str:
        return _image_source(v)


def _image_source(v: str) -> str:
    """An https:// image link, or an image uploaded in the admin panel (/api/v1/agent/media/<id>, v4.15.1)."""
    from app.services.media_store import is_media_path
    v = (v or "").strip()
    if v and not (re.fullmatch(r"https://[^\s\"'<>]+", v) or is_media_path(v)):
        raise ValueError("images must be an https:// link or an uploaded image")
    return v


# One example, switched off: the admissions team writes and switches on its own ads.
DEFAULT_CHAT_ADS = [
    {"id": "admissions-2027", "title": "Admissions open for 2027-28", "subtitle": "Merit scholarships up to 40%",
     "tag": "Apply now", "image_url": f"{_IMG}/2026/10/campus-auditorium5-scaled.webp", "cta_text": "Apply",
     "link_url": "https://apply.sru.edu.in", "enabled": False},
]


class ChatSettings(BaseModel):
    """Every switch, with its default. Field descriptions are shown in the admin panel."""

    concession_picker: Literal["grouped", "table"] = Field(
        "grouped",
        description="How special concessions are shown: 'grouped' (5 folded groups + 'None of these apply') "
                    "or 'table' (all 19 rows).")
    connect_enabled: bool = Field(
        True, description="'Talk to a counsellor' rings the admin panel and waits before arranging a callback.")
    fee_questions: Literal["evaluate_first", "fee_card"] = Field(
        "evaluate_first",
        description="A fee question ('B.Tech CSE fees'): 'evaluate_first' checks the student's marks and eligibility, "
                    "merit scholarship and special concessions, then gives the final fee (a 'Just show the fee' "
                    "button gives the standard fee at once); 'fee_card' shows the standard fee card at once.")
    suggestion_chips: Literal["questions_only", "always"] = Field(
        "questions_only",
        description="Quick-response buttons under an answer: 'questions_only' (when SRU Buddy asks the student "
                    "something, plus the answer options of a step) or 'always' (after every answer).")
    welcome_tiles: list[WelcomeTile] = Field(
        default_factory=lambda: [WelcomeTile(**t) for t in DEFAULT_WELCOME_TILES],
        description="The Quick Start tiles under the opening welcome message, in order (at most 8).")
    event_highlights: list[EventHighlight] = Field(
        default_factory=lambda: [EventHighlight(**e) for e in DEFAULT_EVENT_HIGHLIGHTS],
        description="The events shown as photo cards when students ask about events, fests or campus life (at most 16).")
    chat_ads: list[ChatAd] = Field(
        default_factory=lambda: [ChatAd(**a) for a in DEFAULT_CHAT_ADS],
        description="Small ads at the bottom of the chat, shown in turn (at most 6; only the ones switched on).")
    ads_rotate_seconds: int = Field(8, ge=4, le=60, description="How long each ad is shown before the next one.")
    videos: VideoSettings = Field(
        default_factory=VideoSettings,
        description="Changes to the official YouTube videos the chat shows: hidden, topic changed, added.")
    ai_answers: bool = Field(
        False, description="Answers written by the AI from the verified facts (on), or the verified texts as they "
                          "are (off: no AI call for them, e.g. when the daily AI quota runs low). Cards, numbers and "
                          "workflows are the same either way.")
    connect_wait_seconds: int = Field(30, ge=10, le=120, description="How long the student waits for a counsellor.")
    office_hours_start: str = Field("09:00", description="Counsellors available from (India time, HH:MM).")
    office_hours_end: str = Field("18:00", description="Counsellors available until (India time, HH:MM).")
    office_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5],
                                   description="Working days, 0 = Monday ... 6 = Sunday.")

    @field_validator("welcome_tiles")
    @classmethod
    def _tiles(cls, v: list) -> list:
        if len(v) > 8:
            raise ValueError("at most 8 Quick Start tiles")
        ids = [t.id for t in v]
        if len(set(ids)) != len(ids):
            raise ValueError("each tile needs its own id")
        return v

    @field_validator("chat_ads")
    @classmethod
    def _ads(cls, v: list) -> list:
        if len(v) > 6:
            raise ValueError("at most 6 ads")
        ids = [a.id for a in v]
        if len(set(ids)) != len(ids):
            raise ValueError("each ad needs its own id")
        for a in v:
            if a.enabled and not a.link_url:
                raise ValueError(f"the ad '{a.title}' needs a link before it is switched on")
        return v

    @field_validator("event_highlights")
    @classmethod
    def _events(cls, v: list) -> list:
        if len(v) > 16:
            raise ValueError("at most 16 events")
        ids = [e.id for e in v]
        if len(set(ids)) != len(ids):
            raise ValueError("each event needs its own id")
        return v

    @field_validator("office_hours_start", "office_hours_end")
    @classmethod
    def _hhmm(cls, v: str) -> str:
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", v or ""):
            raise ValueError("use HH:MM, 24-hour (for example 09:00)")
        return v

    @field_validator("office_days")
    @classmethod
    def _days(cls, v: list[int]) -> list[int]:
        days = sorted(set(v))
        if any(d < 0 or d > 6 for d in days):
            raise ValueError("days are 0 (Monday) to 6 (Sunday)")
        return days


_cache: dict[str, Any] = ChatSettings().model_dump()
_loaded_at = 0.0
_meta: dict[str, Any] = {"updated_at": None}
_SETTINGS_REDIS_KEY = "sru:app_settings"


def _get_redis():
    try:
        from app.sru_agent import memory
        return memory.get_redis()
    except Exception:
        return None


def get(name: str) -> Any:
    """The current value of one setting (from the cache; never raises)."""
    return _cache.get(name, ChatSettings.model_fields[name].get_default(call_default_factory=True))


def current() -> dict:
    return dict(_cache)


def meta() -> dict:
    return dict(_meta)


async def refresh(force: bool = False) -> dict:
    """Reload from Redis/database when the cache is older than CACHE_SECONDS (or when forced)."""
    global _loaded_at
    if not force and time.monotonic() - _loaded_at < CACHE_SECONDS:
        return current()
    r = _get_redis()
    if not force and r is not None:
        try:
            raw = await r.get(_SETTINGS_REDIS_KEY)
            if raw:
                data = json.loads(raw)
                _cache.update(ChatSettings(**data).model_dump())
                _loaded_at = time.monotonic()
                return current()
        except Exception:
            pass
    _loaded_at = time.monotonic()
    try:
        from sqlalchemy import select

        from app.db.session import async_session_factory
        from app.models.memory import UserMemory

        async with async_session_factory() as db:
            rows = (await db.execute(select(UserMemory).where(UserMemory.session_id == SYSTEM_SESSION))).scalars().all()
        stored, pieces = {}, {}
        latest = None
        for row in rows:
            if not row.memory_key.startswith(PREFIX):
                continue
            name = row.memory_key[len(PREFIX):]
            if "#" in name:
                key, _, idx = name.partition("#")
                pieces.setdefault(key, {})[int(idx)] = row.memory_value
                continue
            try:
                stored[name] = json.loads(row.memory_value)
            except (TypeError, ValueError):
                continue
            if row.updated_at and (latest is None or row.updated_at > latest):
                latest = row.updated_at
        for key, value in list(stored.items()):
            if isinstance(value, dict) and set(value) == {"__pieces__"}:
                try:
                    parts = pieces.get(key) or {}
                    stored[key] = json.loads("".join(parts[i] for i in range(int(value["__pieces__"]))))
                except (KeyError, TypeError, ValueError):
                    stored.pop(key, None)   # incomplete: the default is used
        merged = {**ChatSettings().model_dump(), **{k: v for k, v in stored.items() if k in ChatSettings.model_fields}}
        _cache.update(ChatSettings(**merged).model_dump())   # a bad stored value falls back to validation error
        _meta["updated_at"] = latest.isoformat() if latest else None
    except Exception as exc:  # database unreachable or a stored value invalid: keep the last known values
        log.warning("chat settings not refreshed (%s); using the last known values", type(exc).__name__)
    return current()


async def update(changes: dict) -> dict:
    """Validate and save some settings. Raises ValueError (with a readable message) on bad values."""
    merged = {**current(), **changes}
    try:
        valid = ChatSettings(**merged).model_dump()
    except Exception as exc:
        raise ValueError(str(exc)) from exc
    changed = {k: valid[k] for k in changes if k in ChatSettings.model_fields}
    try:
        from sqlalchemy import select

        from app.db.session import async_session_factory
        from app.models.memory import UserMemory

        async with async_session_factory() as db:
            rows = (await db.execute(select(UserMemory).where(UserMemory.session_id == SYSTEM_SESSION))).scalars().all()
            existing = {row.memory_key: row for row in rows}

            def put(memory_key: str, text: str):
                row = existing.get(memory_key)
                if row is None:
                    db.add(UserMemory(id=uuid.uuid4(), session_id=SYSTEM_SESSION, memory_key=memory_key,
                                      memory_value=text, consented=True))
                else:
                    row.memory_value = text

            for key, value in changed.items():
                encoded = json.dumps(value, ensure_ascii=False)
                parts = [encoded[i:i + CHUNK] for i in range(0, len(encoded), CHUNK)] if len(encoded) > CHUNK else []
                put(PREFIX + key, json.dumps({"__pieces__": len(parts)}) if parts else encoded)
                for i, part in enumerate(parts):
                    put(f"{PREFIX}{key}#{i}", part)
                for mkey, row in existing.items():   # pieces left over from a longer earlier value
                    if mkey.startswith(f"{PREFIX}{key}#") and int(mkey.rsplit("#", 1)[1]) >= len(parts):
                        await db.delete(row)
            await db.commit()
    except Exception as exc:
        raise RuntimeError("The settings could not be saved right now. Please try again.") from exc
    _cache.update(valid)
    global _loaded_at
    _loaded_at = time.monotonic()
    _meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    r = _get_redis()
    if r is not None:
        try:
            await r.set(_SETTINGS_REDIS_KEY, json.dumps(valid, ensure_ascii=False), ex=CACHE_SECONDS)
        except Exception:
            pass
    return current()


def set_for_tests(**values) -> None:
    """Tests only: set values in the cache without a database."""
    global _loaded_at
    _cache.update(ChatSettings(**{**current(), **values}).model_dump())
    _loaded_at = time.monotonic() + 10_000


def reset_for_tests() -> None:
    global _loaded_at
    _cache.clear()
    _cache.update(ChatSettings().model_dump())
    _loaded_at = 0.0
