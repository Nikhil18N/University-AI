"""
Parser for the SRU university data DOCX.

Actual document structure observed:
  - style='Title'     → top-level section heading (e.g. "Admissions", "Notifications")
  - style='Normal', bold=True, short text → question (or sub-section label)
  - style='Normal', bold=False → answer paragraph (may be multi-paragraph)
  - Bare URL line     → page URL associated with the preceding block of questions

A "question" is a bold Normal paragraph that reads like a question
(contains "?" or is clearly interrogative). Bold Normal paragraphs
without "?" are treated as sub-section labels.

Entries with blank/empty answers are skipped.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_RE_URL = re.compile(r"^https?://\S+$", re.IGNORECASE)
_BLANK_MARKERS = {"", "n/a", "not available", "tbd", "to be updated", "-", "\u2013", "none"}


@dataclass
class ParsedEntry:
    section: str
    sub_section: str
    page_url: str | None
    question: str
    answer: str
    chunk_text: str = field(init=False)

    def __post_init__(self) -> None:
        label = self.sub_section or self.section
        parts = [f"Section: {label}"]
        if self.page_url:
            parts.append(f"Source URL: {self.page_url}")
        parts.append(f"Q: {self.question}")
        parts.append(f"A: {self.answer}")
        self.chunk_text = "\n".join(parts)


def _is_blank(text: str) -> bool:
    return text.strip().lower() in _BLANK_MARKERS


def _looks_like_question(text: str) -> bool:
    """Heuristic: bold paragraph that is likely a question."""
    text = text.strip()
    if not text:
        return False
    # Has a question mark, or starts with a WH-word / common question starters
    if "?" in text:
        return True
    starters = ("what", "when", "where", "who", "how", "why", "can", "is", "are",
                 "do", "does", "will", "which", "should", "could", "has", "have")
    return text.lower().split()[0] in starters if text else False


def _para_is_bold(para) -> bool:
    """True if ALL non-empty runs in the paragraph are bold."""
    runs = [r for r in para.runs if r.text.strip()]
    return bool(runs) and all(r.bold for r in runs)


def parse_university_docx(file_path: Path) -> list[ParsedEntry]:
    """
    Parse the SRU university DOCX and return ParsedEntry objects.
    Entries with blank answers are skipped.
    """
    try:
        from docx import Document as DocxDocument
    except ImportError as e:
        raise ImportError("python-docx is required: pip install python-docx") from e

    doc = DocxDocument(str(file_path))
    entries: list[ParsedEntry] = []

    current_section = "General"
    current_sub_section = ""
    current_page_url: str | None = None

    # Q&A state
    pending_question: str | None = None
    answer_lines: list[str] = []
    # Track URL lines that appear AFTER a question block (applies to that block's section)
    pending_url_update: str | None = None

    def _flush() -> None:
        nonlocal pending_question, answer_lines
        if pending_question is None:
            return
        answer_text = " ".join(l for l in answer_lines if l).strip()
        if not _is_blank(answer_text):
            entries.append(ParsedEntry(
                section=current_section,
                sub_section=current_sub_section,
                page_url=current_page_url,
                question=pending_question,
                answer=answer_text,
            ))
        else:
            logger.debug(
                "Skipping unanswered Q in [%s > %s]: %s",
                current_section, current_sub_section, pending_question[:80],
            )
        pending_question = None
        answer_lines.clear()

    for para in doc.paragraphs:
        raw = para.text.strip()
        if not raw:
            continue

        style_name = para.style.name or ""

        # ── Top-level section (Title style) ───────────────────────────────
        if style_name == "Title":
            _flush()
            current_section = raw
            current_sub_section = ""
            current_page_url = None
            logger.debug("Section: %s", current_section)
            continue

        # ── Heading styles ─────────────────────────────────────────────────
        if "Heading" in style_name:
            _flush()
            current_sub_section = raw
            current_page_url = None
            logger.debug("Sub-section: %s", current_sub_section)
            continue

        # ── Bare URL line ──────────────────────────────────────────────────
        if _RE_URL.match(raw):
            # URL that follows a block — assign to current section context
            current_page_url = raw.rstrip(".,;)")
            logger.debug("URL for [%s]: %s", current_section, current_page_url)
            continue

        # ── Bold Normal paragraph → question or sub-section label ──────────
        is_bold = _para_is_bold(para)
        if is_bold and style_name == "Normal":
            if _looks_like_question(raw):
                # It's a question
                _flush()
                pending_question = raw
                answer_lines = []
            else:
                # It's a sub-section label
                _flush()
                current_sub_section = raw
                logger.debug("Sub-section: %s", current_sub_section)
            continue

        # ── Non-bold Normal → answer line (or continuation) ───────────────
        if pending_question is not None:
            answer_lines.append(raw)

    _flush()  # flush last entry

    logger.info(
        "Parsed %d answerable Q&A entries from '%s'",
        len(entries), file_path.name,
    )
    return entries
