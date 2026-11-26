"""Self-check for answers written by the language model (v4.12.0).

Before an AI-written answer is sent, its numbers are checked against what the code knows for this turn:
  * a scholarship percentage stated next to the student's own fee calculation must be the calculator's;
    a different one is corrected;
  * every rupee amount must appear in a verified source of this turn (the fee calculation, the cards, the
    handbook / facts passages) or in the official fee data; if one does not, a short note asks the student to
    confirm with the Admissions Office (the text is not silently rewritten).
Answers written by the code itself come from the same data and pass unchanged.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from . import config, fees

_RUPEES = re.compile(r"(?:₹|rs\.?|inr)\s?(\d[\d,]*(?:\.\d+)?)", re.IGNORECASE)
# Salaries, stipends and funding ("₹44 LPA", "₹1.25L/month", "₹76+ Cr") are not fees: never checked as fee amounts.
_NOT_A_FEE = re.compile(r"\s*\+?\s*(?:lpa\b|l\b|lakhs?\b|lacs?\b|cr\b|crores?\b|k\b|/\s*(?:month|mo)\b|per\s+month\b)",
                        re.IGNORECASE)
_PCT_SCHOLARSHIP = re.compile(r"\b(\d{1,3})\s?%\s*(?:merit\s+)?(?:scholarship|waiver|fee\s+waiver)", re.IGNORECASE)
NOTE = ("\n\n_I couldn't verify every amount above against the official fee data; please confirm with the "
        "Admissions Office ({phone})._")


def _amounts(text: str) -> set[int]:
    out = set()
    for m in _RUPEES.finditer(text or ""):
        if _NOT_A_FEE.match(text, m.end()):
            continue
        digits = m.group(1).replace(",", "").split(".")[0]
        if digits.isdigit():
            out.add(int(digits))
    return out


@lru_cache(maxsize=1)
def _fee_data_amounts() -> frozenset[int]:
    """Every whole-rupee number in the official fee data, plus halves (per semester)."""
    found: set[int] = set()

    def walk(v):
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)) and v >= 1000:
            found.add(int(v))
            found.add(int(v) // 2)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, str):
            found.update(_amounts(v))

    walk(fees.load_data())
    found |= _engine_amounts()
    return frozenset(found)


def _engine_amounts() -> set[int]:
    """Every total the ONE fee engine can produce for a programme, slab and option (semester and year payables,
    course totals, per-year tuition): figures computed from the policy are verified figures."""
    found: set[int] = set()
    data = fees.load_data()
    pcts = sorted({0} | {s["percent"] for sets in data["slab_sets"].values() for t in sets.values() for s in t})
    for key in data["programs"]:
        for pct in pcts:
            for hostel in [None] + list(fees.hostel_per_year()):
                for bus in (False, True):
                    plan = fees.fee_schedule(key, pct, hostel=hostel, transport=bus)
                    for y in plan["years"]:
                        found.update({y["total"], y["annual_tuition"], y["scholarship"], y["tuition_before_scholarship"]})
                        for sem in y["semesters"]:
                            found.add(sem["total"])
                            found.update(abs(i["amount"]) for i in sem["items"])
                    if plan["course_total"]:
                        found.add(plan["course_total"])
    return {a for a in found if a >= 1000}


def check(text: str, *, fee_result: dict | None = None, sources: list | None = None) -> tuple[str, list[str]]:
    """(text to send, problems found). `sources`: strings or JSON-able objects verified for this turn."""
    if not text:
        return text, []
    problems = []
    out = text
    if fee_result and fee_result.get("status") == "ok":
        right = int(fee_result.get("scholarship_percent") or 0)

        def fix(m):
            n = int(m.group(1))
            ctx_window = out[max(0, m.start() - 35): min(len(out), m.end() + 45)]
            if _NEGATED.search(ctx_window) or re.search(
                r"\b(?:not\s+applicable|not\s+offered|not\s+available|maximum|up\s+to|next\s+(?:tier|slab)|above|highest|range)\b",
                ctx_window,
                re.I,
            ):
                return m.group(0)
            if n != right and right > 0:
                problems.append(f"scholarship {n}% -> {right}%")
                return m.group(0).replace(m.group(1), str(right), 1)
            return m.group(0)

        out = _PCT_SCHOLARSHIP.sub(fix, out)
    verified = set(_fee_data_amounts())
    for src in list(sources or []) + ([fee_result] if fee_result else []):
        verified |= _amounts(src if isinstance(src, str) else json.dumps(src, ensure_ascii=False, default=str))
    unknown = sorted(a for a in _amounts(out) if a not in verified)
    if unknown:
        problems.append("unverified amounts: " + ", ".join(fees.inr(a) for a in unknown[:5]))
        out = out.rstrip() + NOTE.format(phone=config.ADMISSIONS_PHONE)
    return out, problems


# ---- v4.17.1: people and the offices they hold -------------------------------------------------------------------
# A name with an honorific ("Dr. Ram Raghotham Rao Deshmukh") must be in this turn's evidence or in the approved
# corpus (faculty directory, handbook, indexed university FAQ); a sentence that says someone holds an office must
# have evidence that pairs that name with that office. Otherwise the sentence is replaced, never shown as a fact.
_PERSON = re.compile(r"\b(?:Dr|Prof|Professor|Mr|Mrs|Ms|Sri|Smt|Col|Lt|Capt)\.?\s+((?:[A-Z][A-Za-z]*\.?\s?){1,5})")
_ROLE_CLAIM = re.compile(
    r"\b(?:(?:Senior|Associate|Assistant|Deputy|Additional|Joint)\s+)?(?:Director|Dean|Head|Registrar|Controller|"
    r"Chancellor|Vice[\s-]Chancellor|Pro[\s-]Vice[\s-]Chancellor|Pro[\s-]Chancellor|CEO|Principal|Warden|Coordinator)"
    r"(?:\s+(?:of|for)\s+(?:the\s+)?([A-Z][\w&\-]*(?:\s+(?:and|&|of|for)?\s*[A-Z][\w&\-]*){0,5}))?")
_NEGATED = re.compile(r"\b(?:not|isn't|is not|no longer|never|neither|nor)\b|n't\b", re.IGNORECASE)
_UNVERIFIED_LINE = "I couldn't verify that detail in SR University's official records."
_corpus_cache: dict = {"at": 0.0, "text": ""}


def _norm_text(text: str) -> str:
    text = re.sub(r"\b(?:dr|prof|professor|mr|mrs|ms|sri|smt|col|lt|capt)\b\.?", " ", (text or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _approved_corpus() -> str:
    """Normalised text of every approved source of names and titles (cached for 10 minutes)."""
    import time
    from pathlib import Path
    if _corpus_cache["text"] and time.time() - _corpus_cache["at"] < 600:
        return _corpus_cache["text"]
    parts = []
    try:
        from . import faculty
        parts += [f"{p['name']} {p.get('role', '')} {p.get('designation', '')}" for p in faculty._data()["faculty"]]
    except Exception:
        pass
    try:
        from app.config import settings
        for path in sorted(Path(settings.DATA_DIR, "handbook").glob("*.md")):
            parts.append(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    try:
        from app.db.chroma import get_chroma_client
        from app.services.rag_service import COLLECTION_NAME
        got = get_chroma_client().get_or_create_collection(name=COLLECTION_NAME).get(include=["documents"])
        parts += [d for d in got.get("documents") or [] if d]
    except Exception:
        pass
    _corpus_cache.update(at=time.time(), text=" \n ".join(_norm_text(p) for p in parts))
    return _corpus_cache["text"]


def _name_tokens(raw: str) -> list[str]:
    return [t for t in _norm_text(raw).split() if len(t) > 2]


def _known_name(tokens: list[str], corpus: str) -> bool:
    """The name's words appear together (in order, at most two words apart) in the evidence."""
    if not tokens:
        return True
    pattern = r"\b" + r"\b(?:\s+\w+){0,2}\s+\b".join(map(re.escape, tokens)) + r"\b"
    return bool(re.search(pattern, corpus))


_ROLE_GENERIC = {"university", "department", "dept", "school", "centre", "center", "engineering", "sciences", "studies"}


def _role_paired(tokens: list[str], office: str, corpus: str) -> bool:
    """Some evidence mentions this person and the core role/subject words within a short distance."""
    office_words = [w[:5] for w in _norm_text(office).split() if len(w) > 3 and w not in _ROLE_GENERIC]
    if not office_words:
        return True
    surname = tokens[-1]
    for m in re.finditer(rf"\b{re.escape(surname)}\b", corpus):
        window = corpus[max(0, m.start() - 260): m.end() + 260]
        found = {w[:5] for w in window.split()}
        if office_words[0] in found and (len(office_words) == 1 or any(w in found for w in office_words[1:])):
            return True
    return False


_ABBREV = re.compile(r"(?:\b(?:Dr|Prof|Mr|Mrs|Ms|Sri|Smt|Col|Lt|Capt|St|No|vs|etc|e\.g|i\.e|Ph\.D|M\.Tech|B\.Tech)|"
                     r"\b[A-Z])\.$")


def _sentences(line: str) -> list[str]:
    """Split a line into sentences, but not after an honorific or an initial ("Dr. Ram", "B. S. Rao")."""
    out, start = [], 0
    for m in re.finditer(r"[.!?](?:\*\*)?\s+", line):
        head = line[start:m.start() + 1]
        if _ABBREV.search(head.rstrip("*")):
            continue
        out.append(line[start:m.end()].rstrip())
        start = m.end()
    out.append(line[start:])
    return [x for x in out if x != ""]


def check_people(text: str, evidence: list | None = None) -> tuple[str, list[str]]:
    """(text, problems): sentences naming a person who is in no approved source, or saying that someone holds an
    office no source pairs them with, are replaced by an honest 'could not verify' line."""
    if not text or not _PERSON.search(text):
        return text, []
    turn = " \n ".join(_norm_text(e if isinstance(e, str) else json.dumps(e, ensure_ascii=False, default=str))
                       for e in (evidence or []) if e)
    corpus = turn + " \n " + _approved_corpus()
    problems, out_lines = [], []
    for line in text.split("\n"):
        sentences = _sentences(line)
        kept = []
        for sent in sentences:
            bad = None
            for m in _PERSON.finditer(sent):
                tokens = _name_tokens(m.group(1))
                if not _known_name(tokens, corpus):
                    bad = f"unverified person: {m.group(0).strip()}"
                    break
                role = _ROLE_CLAIM.search(sent[m.end():] + " " + sent[:m.start()])
                if role and role.group(1) and not _NEGATED.search(sent) and not _role_paired(tokens, role.group(0), corpus):
                    bad = f"unverified role: {m.group(0).strip()} as {role.group(0).strip()}"
                    break
            if bad:
                problems.append(bad)
                prefix = re.match(r"\s*(?:[-*•]\s+|\d+\.\s+)?", sent).group(0)
                kept.append(prefix + _UNVERIFIED_LINE)
            else:
                kept.append(sent)
        out_lines.append(" ".join(kept))
    out = "\n".join(out_lines)
    if problems:
        dedup = []
        for ln in out.split("\n"):
            if ln.strip().lstrip("-*• ").startswith(_UNVERIFIED_LINE) and dedup and dedup[-1].strip().lstrip("-*• ").startswith(_UNVERIFIED_LINE):
                continue
            dedup.append(ln)
        out = "\n".join(dedup)
        if config.ADMISSIONS_PHONE not in out:
            out = out.rstrip() + f"\n\nThe Admissions Office ({config.ADMISSIONS_PHONE}) can confirm it."
    return out, problems
