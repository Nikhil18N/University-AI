"""Unit tests for document ingestion utilities."""

from pathlib import Path
from app.services.ingestion_service import (
    _compute_checksum,
    _chunk_text,
    _extract_text_from_txt,
)


def test_checksum_computation():
    content = b"University Examination Guidelines 2026"
    checksum1 = _compute_checksum(content)
    checksum2 = _compute_checksum(content)
    assert checksum1 == checksum2
    assert len(checksum1) == 64  # SHA-256 hex digest length


def test_chunking_short_text():
    text = "Short policy document with just a few words."
    chunks = _chunk_text(text, chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunking_multiparagraph():
    paragraphs = [f"Paragraph {i} content with some description." for i in range(10)]
    full_text = "\n\n".join(paragraphs)
    chunks = _chunk_text(full_text, chunk_size=15, overlap=5)
    assert len(chunks) > 1
    # Check that all chunks contain text
    for c in chunks:
        assert len(c.strip()) > 0


def test_extract_text_from_txt(tmp_path: Path):
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Hello University AI", encoding="utf-8")
    pages = _extract_text_from_txt(txt_file)
    assert len(pages) == 1
    assert pages[0]["page"] == 1
    assert pages[0]["text"] == "Hello University AI"
