"""Search the SR University handbook WITHOUT calling any AI service.

Why this exists: the vector search needs one Gemini "embedding" call for every question and one
per chunk when the server starts with an empty index. On the free Gemini tier that quota runs out,
the index stays empty, and the agent answers without the handbook. This module reads the handbook
files straight from disk and ranks passages with BM25 (plain keyword scoring), so the agent always
has its knowledge: on a cold start, in a brand-new chat, and when the AI quota is used up.

    from app.sru_agent import knowledge
    knowledge.search("hostel in-time for first years")  ->  [{"title", "text", "source", "score"}, ...]

To add knowledge: put a .md file in backend/data/handbook/ and restart (or call knowledge.reload()).
"""
import math
import os
import re
from pathlib import Path

_STOP = frozenset("""
a an the is are was were be been am do does did of in on at to for from with by as and or but if
then so it its this that these those there here i me my we our you your he she they them his her
what which who whom whose when where why how can could would should will shall may might must
tell know want need please pls give get show about any some all also just very much many more
sr sru university campus student students have has had not no yes
""".split())

# Words students use -> words the handbook uses. Applied to the QUESTION only.
_SYNONYMS = {
    "fees": ["fee"], "fess": ["fee"], "cost": ["fee", "tuition"], "price": ["fee"], "tuition": ["fee"],
    "scholarships": ["scholarship"], "scholorship": ["scholarship"], "concession": ["scholarship", "concessions"],
    "discount": ["scholarship"], "waiver": ["scholarship"],
    "eamcet": ["eapcet"], "emcet": ["eapcet"], "emact": ["eapcet"], "eamect": ["eapcet"],
    "curfew": ["in-time", "intime", "timings", "hostel"], "intime": ["in-time", "hostel"],
    "timing": ["timings"], "outing": ["hostel", "outings"],
    "placements": ["placement", "package", "lpa"], "placement": ["package", "lpa", "recruiters"],
    "package": ["lpa", "placement"], "salary": ["lpa", "package", "placement"], "job": ["placement"],
    "jobs": ["placement"], "companies": ["recruiters", "placement"], "recruiters": ["placement"],
    "owner": ["chancellor", "founder", "society"], "founder": ["chancellor", "society", "established"],
    "chairman": ["chancellor"], "vc": ["vice", "chancellor"], "head": ["chancellor"],
    "bus": ["transport"], "buses": ["transport"], "transportation": ["transport"],
    "ragging": ["anti-ragging", "discipline"], "safe": ["security", "safety"], "safety": ["security"],
    "food": ["dining", "mess"], "mess": ["dining"], "canteen": ["dining", "cafeteria"],
    "documents": ["certificates", "document"], "docs": ["certificates", "documents"],
    "certificates": ["documents"], "location": ["warangal", "ananthasagar", "address"],
    "address": ["warangal", "ananthasagar"], "located": ["warangal", "ananthasagar"],
    "ranking": ["nirf", "rank", "qs"], "rankings": ["nirf", "rank", "qs"], "rank": ["nirf", "ranking"],
    "accreditation": ["nba", "naac", "ugc", "icar"], "approved": ["ugc", "aicte"], "valid": ["ugc", "recognised"],
    "recognised": ["ugc"], "recognized": ["ugc", "recognised"], "fake": ["ugc", "recognised"],
    "attendance": ["detention", "condonation"], "backlog": ["supplementary", "examination"],
    "exam": ["examination"], "exams": ["examination"], "grading": ["cgpa", "grade"],
    "phd": ["ph.d", "doctoral", "research"], "abroad": ["international", "iep"], "foreign": ["international"],
    "gym": ["sports", "fitness"], "library": ["library"], "wifi": ["wi-fi"], "laundry": ["laundry"],
    "refund": ["refund", "withdrawal"], "cancel": ["refund", "withdrawal"], "loan": ["loan", "bank"],
    "branches": ["programs", "b.tech"], "courses": ["programs"], "course": ["program"],
    "cse": ["computer", "science"], "aiml": ["ai", "ml"], "eligibility": ["eligible", "minimum"],
    "cutoff": ["minimum", "eligibility"], "apply": ["application", "admission"], "admission": ["admissions"],
    "startup": ["srix", "incubation"], "incubator": ["srix"], "clubs": ["club", "student"],
    "girls": ["girls", "women"], "boys": ["boys"], "ac": ["ac"], "room": ["sharing", "hostel"],
    "mtech": ["m.tech"], "btech": ["b.tech"], "bsc": ["b.sc"], "msc": ["m.sc"], "bcom": ["b.com"],
    "bdes": ["b.des"], "degree": ["ugc", "recognised", "2(f)"], "runs": ["chancellor", "society"],
    "own": ["chancellor", "society", "sponsoring"], "owns": ["chancellor", "society", "sponsoring"],
    "management": ["chancellor", "society", "leadership"], "principal": ["vice-chancellor", "registrar"],
    "dean": ["leadership"], "process": ["apply", "register", "admission"], "steps": ["apply", "register"],
}
_WORD = re.compile(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*")

_chunks: list = []        # [{"title", "text", "source", "tokens": {term: count}, "length": int}]
_doc_freq: dict = {}
_avg_len = 1.0
_loaded_from = None


def _handbook_dir():
    here = Path(__file__).resolve()
    candidates = [os.getenv("SRU_HANDBOOK_DIR"), here.parents[2] / "data" / "handbook",
                  here.parents[3] / "data" / "handbook", Path.cwd() / "data" / "handbook",
                  Path.cwd() / "backend" / "data" / "handbook"]
    for c in candidates:
        if c and Path(c).is_dir():
            return Path(c)
    return None


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _tokens(text: str) -> list:
    out = []
    for word in _WORD.findall(text.lower()):
        for part in {word, *re.split(r"[.\-]", word)}:
            if part and part not in _STOP and (len(part) > 1 or part.isdigit()):
                out.append(_stem(part))
    return out


def _split(md: str, source: str) -> list:
    """Cut a markdown file into passages of one topic each, remembering the headings above them."""
    chunks, path, buf = [], [], []

    def flush():
        text = "\n".join(buf).strip()
        buf.clear()
        if len(text) < 40:
            return
        title = " > ".join(p for p in path if p)
        # long sections: cut at blank lines / fact bullets so one passage stays readable
        parts, current = [], ""
        for block in re.split(r"\n\s*\n|\n(?=- \*\*\[FACT-ID)", text):
            if current and len(current) + len(block) > 1500:
                parts.append(current)
                current = ""
            current = (current + "\n\n" + block).strip()
        if current:
            parts.append(current)
        for part in parts:
            if len(part) <= 1800:
                chunks.append({"title": title, "text": part, "source": source})
                continue
            # one very long bullet (a "fact" with many sub-points): cut at its sub-bullets and keep
            # the first line (the fact's label) on every piece
            lines = part.split("\n")
            head, piece = lines[0], ""
            for line in lines[1:]:
                if piece and len(piece) + len(line) > 1100 and re.match(r"^\s{0,4}[-*] ", line):
                    chunks.append({"title": title, "text": head + "\n" + piece.rstrip(), "source": source})
                    piece = ""
                piece += line + "\n"
            if piece.strip():
                chunks.append({"title": title, "text": head + "\n" + piece.rstrip(), "source": source})

    for line in md.splitlines():
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            flush()
            level = len(m.group(1))
            path[:] = path[:level - 1] + [""] * max(0, level - 1 - len(path)) + [m.group(2).strip(" #*")]
        elif not line.startswith("---") or buf:
            buf.append(line)
    flush()
    return chunks


def reload(directory=None) -> int:
    """(Re)read the handbook from disk. Returns the number of passages indexed."""
    global _chunks, _doc_freq, _avg_len, _loaded_from
    directory = Path(directory) if directory else _handbook_dir()
    chunks = []
    if directory and directory.is_dir():
        for path in sorted(directory.glob("*.md")):
            try:
                chunks += _split(path.read_text(encoding="utf-8"), path.name)
            except OSError:
                continue
    doc_freq = {}
    for chunk in chunks:
        counts = {}
        for tok in _tokens(chunk["text"]) + _tokens(chunk["title"]) * 3:  # headings count three times
            counts[tok] = counts.get(tok, 0) + 1
        chunk["tokens"], chunk["length"] = counts, sum(counts.values())
        for tok in counts:
            doc_freq[tok] = doc_freq.get(tok, 0) + 1
    _chunks, _doc_freq = chunks, doc_freq
    _avg_len = (sum(c["length"] for c in chunks) / len(chunks)) if chunks else 1.0
    _loaded_from = directory
    return len(chunks)


def _ensure_loaded():
    if _loaded_from is None:
        reload()


def query_terms(question: str) -> list:
    """The question's keywords plus the handbook's words for them."""
    terms = []
    for word in _WORD.findall((question or "").lower()):
        base = _stem(word)
        if word in _STOP and word not in _SYNONYMS:
            continue
        if base not in _STOP:
            terms.append(base)
        for extra in _SYNONYMS.get(word, []) + _SYNONYMS.get(base, []):
            terms += [(_stem(t), 0.6) for t in _WORD.findall(extra)]
    weighted = {}
    for t in terms:
        term, weight = (t, 1.0) if isinstance(t, str) else t
        weighted[term] = max(weighted.get(term, 0), weight)
    return list(weighted.items())


def search(question: str, k: int = 4, min_score: float = 0.0) -> list:
    """Best handbook passages for a question: [{"title", "text", "source", "score"}], best first."""
    _ensure_loaded()
    terms = query_terms(question)
    if not terms or not _chunks:
        return []
    n = len(_chunks)
    scored = []
    for chunk in _chunks:
        score, hits = 0.0, 0
        for term, weight in terms:
            tf = chunk["tokens"].get(term)
            if not tf:
                continue
            hits += weight
            idf = math.log(1 + (n - _doc_freq[term] + 0.5) / (_doc_freq[term] + 0.5))
            score += weight * idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * chunk["length"] / _avg_len))
        if score:
            # passages that cover more of the question's words rank above ones repeating a single word
            score *= 0.6 + 0.4 * min(1.0, hits / max(1.0, sum(w for _, w in terms if w == 1.0) or 1.0))
            scored.append((score, chunk))
    scored.sort(key=lambda pair: -pair[0])
    return [{"title": c["title"], "text": c["text"], "source": c["source"], "score": round(s, 2)}
            for s, c in scored[:k] if s >= min_score]


def size() -> int:
    _ensure_loaded()
    return len(_chunks)
