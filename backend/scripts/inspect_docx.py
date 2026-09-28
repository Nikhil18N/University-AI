"""Quick script to dump the raw paragraph structure of a DOCX for inspection."""
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND))

from docx import Document

path = Path(r"c:\Users\nikhi\Projects\University-AI\data\SRU Agentic AI.docx")
doc = Document(str(path))

print(f"Total paragraphs: {len(doc.paragraphs)}\n")
for i, para in enumerate(doc.paragraphs[:80]):  # first 80 paragraphs
    style = para.style.name
    text = para.text.strip()
    bold_runs = [r.text for r in para.runs if r.bold and r.text.strip()]
    if text:
        print(f"[{i:03d}] style={style!r:30s} bold_parts={bool(bold_runs)} | {text[:120]}")
