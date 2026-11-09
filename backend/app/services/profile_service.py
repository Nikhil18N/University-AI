"""Student profile extraction and dynamic counsellor guidance service."""

import re
from typing import Any

DEGREE_PATTERNS = [
    (re.compile(r"\b(b\.?\s*tech|bachelor\s+of\s+technology)\b", re.I), "B.Tech"),
    (re.compile(r"\b(m\.?\s*tech|master\s+of\s+technology)\b", re.I), "M.Tech"),
    (re.compile(r"\b(mba|master\s+of\s+business\s+administration)\b", re.I), "MBA"),
    (re.compile(r"\b(bba|bachelor\s+of\s+business\s+administration)\b", re.I), "BBA"),
    (re.compile(r"\b(mca|master\s+of\s+computer\s+applications)\b", re.I), "MCA"),
    (re.compile(r"\b(ph\.?\s*d|doctorate|research\s+scholar)\b", re.I), "Ph.D."),
    (re.compile(r"\b(b\.?\s*sc|bachelor\s+of\s+science)\b", re.I), "B.Sc"),
    (re.compile(r"\b(agriculture|agri)\b", re.I), "Agriculture"),
]

BRANCH_PATTERNS = [
    (re.compile(r"\b(ai\s*(&|and|\+)?\s*ml|artificial\s+intelligence\s+(and|&)?\s*machine\s+learning)\b", re.I), "AI & Machine Learning"),
    (re.compile(r"\b(data\s+science|ds|big\s+data)\b", re.I), "Data Science"),
    (re.compile(r"\b(cyber\s+security|infosec)\b", re.I), "Cyber Security"),
    (re.compile(r"\b(cse|computer\s+science(\s+and\s+engineering)?|cs)\b", re.I), "Computer Science & Engineering (CSE)"),
    (re.compile(r"\b(ece|electronics(\s+and\s+communication(\s+engineering)?)?)\b", re.I), "Electronics & Communication Engineering (ECE)"),
    (re.compile(r"\b(eee|electrical(\s+and\s+electronics(\s+engineering)?)?)\b", re.I), "Electrical & Electronics Engineering (EEE)"),
    (re.compile(r"\b(mech|mechanical(\s+engineering)?)\b", re.I), "Mechanical Engineering"),
    (re.compile(r"\b(civil(\s+engineering)?)\b", re.I), "Civil Engineering"),
]

SCORE_PERCENT_PATTERN = re.compile(r"\b(\d{1,2}(?:\.\d+)?)\s*%", re.I)
SCORE_PERCENT_WORD_PATTERN = re.compile(r"\b(\d{1,2}(?:\.\d+)?)\s*(?:percent|percentage|pct)\b", re.I)
SCORE_FRACTION_PATTERN = re.compile(r"\b(\d{2,4})\s*(?:out\s+of|/)\s*(\d{2,4})\b", re.I)
SCORE_VERB_KEYWORD_PATTERN = re.compile(
    r"\b(?:got|scored|have|with|secured|my\s+marks?\s*(?:is|are)?|marks?\s*(?:is|are)?|score\s*(?:is|are)?)\s*[:=]?\s*(\d{2}(?:\.\d+)?)\b",
    re.I,
)
SCORE_SUBJECT_KEYWORD_PATTERN = re.compile(
    r"\b(?:12th|10\+2|inter|intermediate|pcm|boards?|class\s*12)\s*(?:marks?|score|percentage)?\s*(?:is|are|of|:)?\s*(\d{2}(?:\.\d+)?)\b",
    re.I,
)
SCORE_NUMBER_BEFORE_SUBJECT_PATTERN = re.compile(
    r"\b(\d{2}(?:\.\d+)?)\s*(?:marks?|%|percent)?\s*(?:in|for|at)\s*(?:12th|10\+2|inter|intermediate|pcm|boards?|class\s*12)\b",
    re.I,
)
SCORE_STANDALONE_ANSWER_PATTERN = re.compile(
    r"^\s*(\d{2}(?:\.\d+)?)\s*(?:marks?|in\s*(?:12th|inter|pcm))?\s*$",
    re.I,
)


COMPARISON_QUERY_PATTERN = re.compile(
    r"\b(vs|versus|compare|comparison|difference\s+between|better\s+between|which\s+is\s+better)\b",
    re.I,
)

CORRECTION_SIGNAL_PATTERN = re.compile(
    r"\b(actually|instead|change|switch|prefer|not|sorry|typo|correction|update|my\s+mistake|now\s+i\s+want|rather)\b",
    re.I,
)


def extract_degree_from_text(text: str) -> str | None:
    """Extract degree from utterance."""
    for pattern, name in DEGREE_PATTERNS:
        if pattern.search(text):
            return name
    return None


def extract_branch_from_text(text: str) -> str | None:
    """Extract branch from utterance, matching specific branch names."""
    for pattern, name in BRANCH_PATTERNS:
        if pattern.search(text):
            return name
    return None


def extract_score_from_text(text: str) -> tuple[float, str] | None:
    """Extract percentage or fractional score from a single utterance."""
    # 1. Percent format: e.g. 85%
    pct_match = SCORE_PERCENT_PATTERN.search(text)
    if pct_match:
        try:
            val = float(pct_match.group(1))
            if 35 <= val <= 100:
                return val, f"{val}%"
        except ValueError:
            pass

    # 2. Word percent format: e.g. 85 percent, 85 percentage
    word_pct_match = SCORE_PERCENT_WORD_PATTERN.search(text)
    if word_pct_match:
        try:
            val = float(word_pct_match.group(1))
            if 35 <= val <= 100:
                return val, f"{val}%"
        except ValueError:
            pass

    # 3. Fraction format: e.g. 450/600 or 920 out of 1000
    frac_match = SCORE_FRACTION_PATTERN.search(text)
    if frac_match:
        try:
            obtained = float(frac_match.group(1))
            total = float(frac_match.group(2))
            if total > 0 and obtained <= total:
                pct = round((obtained / total) * 100, 1)
                return pct, f"{obtained}/{total} ({pct}%)"
        except ValueError:
            pass

    # 4. Contextual verbs: e.g. "i got 85 in 12th", "my marks is 85"
    verb_match = SCORE_VERB_KEYWORD_PATTERN.search(text)
    if verb_match:
        try:
            val = float(verb_match.group(1))
            if 35 <= val <= 100:
                return val, f"{val}%"
        except ValueError:
            pass

    # 5. Contextual subjects: e.g. "12th marks 85", "inter 78"
    subj_match = SCORE_SUBJECT_KEYWORD_PATTERN.search(text)
    if subj_match:
        try:
            val = float(subj_match.group(1))
            if 35 <= val <= 100:
                return val, f"{val}%"
        except ValueError:
            pass

    # 5.5 Number before subject: e.g. "78 in pcm", "85 in 12th"
    num_subj_match = SCORE_NUMBER_BEFORE_SUBJECT_PATTERN.search(text)
    if num_subj_match:
        try:
            val = float(num_subj_match.group(1))
            if 35 <= val <= 100:
                return val, f"{val}%"
        except ValueError:
            pass

    # 6. Standalone answer: e.g. user just types "85" or "85 marks"
    standalone_match = SCORE_STANDALONE_ANSWER_PATTERN.match(text)
    if standalone_match:
        try:
            val = float(standalone_match.group(1))
            if 35 <= val <= 100:
                return val, f"{val}%"
        except ValueError:
            pass

    return None


def extract_student_profile(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Scan user messages in chronological order and maintain verified student profile slots.

    Supports:
    - Initial slot filling (degree, branch, score)
    - Slot corrections (e.g. 'actually ece', 'not cse, change to ece', 'sorry typo my score is 75%')
    - Dialogue preservation across topic-switching interruptions (e.g. hostel inquiries mid-flow)
    - Comparative query discrimination (e.g. 'compare CSE vs ECE' does not overwrite existing branch)
    """
    profile = {
        "degree": None,
        "branch": None,
        "score_pct": None,
        "score_raw": None,
        "has_score": False,
    }

    user_texts = [m["content"] for m in messages if m.get("role") == "user"]

    for text in user_texts:
        is_comparison = bool(COMPARISON_QUERY_PATTERN.search(text))
        has_correction = bool(CORRECTION_SIGNAL_PATTERN.search(text))

        # Check Degree
        deg = extract_degree_from_text(text)
        if deg:
            if not profile["degree"] or has_correction or "instead" in text.lower() or "switch" in text.lower():
                profile["degree"] = deg

        # Check Branch: do not overwrite on comparison queries (e.g. 'compare CSE vs ECE')
        if not is_comparison:
            br = extract_branch_from_text(text)
            if br:
                if (
                    not profile["branch"]
                    or has_correction
                    or "instead" in text.lower()
                    or "switch" in text.lower()
                    or "change" in text.lower()
                    or "want" in text.lower()
                ):
                    profile["branch"] = br

        # Check Score: update if new or corrected score is provided
        score_res = extract_score_from_text(text)
        if score_res:
            val, raw = score_res
            profile["score_pct"] = val
            profile["score_raw"] = raw
            profile["has_score"] = True

    return profile


ELIGIBILITY_INTENT_PATTERN = re.compile(
    r"\b(eligible|eligibility|qualify|qualifying|cutoff|cut\s*off|minimum\s+marks|percentage\s+required|"
    r"can\s+i\s+(get\s+admission|join|apply)|am\s+i\s+eligible|admission\s+criteria|"
    r"how\s+to\s+get\s+admission|admission\s+procedure|admission\s+process|how\s+can\s+i\s+join)\b",
    re.IGNORECASE,
)


def build_counsellor_guidance(profile: dict[str, Any], current_query: str = "") -> str:
    """Generate unambiguous contextual directives for the RAG prompt based on known slots."""
    directives = []

    degree = profile.get("degree")
    branch = profile.get("branch")
    has_score = profile.get("has_score", False)
    score_pct = profile.get("score_pct")
    score_raw = profile.get("score_raw")

    if not degree and not branch and not has_score:
        return ""

    directives.append("VERIFIED STUDENT CONVERSATION CONTEXT:")
    if degree:
        directives.append(f"- Intended Degree: {degree} (ALREADY specified by student — DO NOT ask what degree or level they want).")
    if branch:
        directives.append(f"- Intended Branch: {branch} (ALREADY specified by student — DO NOT ask what branch or specialization they want).")

    if has_score and score_pct is not None:
        directives.append(f"- Stated 12th/Intermediate Score: {score_raw} (ALREADY PROVIDED — DO NOT ask for their score or percentage again!).")
        cutoff = 60.0  # SRU general cutoff for B.Tech
        if score_pct >= cutoff:
            directives.append(
                f"- Cutoff Evaluation: The student's score of {score_raw} is >= {cutoff:.0f}% cutoff. "
                "CONFIRM DIRECTLY THAT THEY ARE ELIGIBLE! Never say they fall short. Do not use outcome-implying phrases ('you're in a great spot', 'you've got this', 'guaranteed admission'). Share program details neutrally."
            )
            directives.append(
                "- Slot Filling for Scholarships: If the student asks for scholarship slabs or waivers, check if their examination board (CBSE vs State Board) is specified. "
                "Never assume CBSE. If the board is unknown, ask which board they studied under before quoting specific slabs."
            )
        else:
            directives.append(
                f"- Cutoff Evaluation: The student's score of {score_raw} is strictly below the {cutoff:.0f}% cutoff. "
                "Politely explain that it falls below the minimum requirement."
            )
    else:
        is_asking_eligibility = bool(current_query and ELIGIBILITY_INTENT_PATTERN.search(current_query))
        directives.append(
            "- Stated Score: NOT PROVIDED YET. NEVER invent or assume any percentage (like 75% or 60%)."
        )
        if is_asking_eligibility:
            directives.append(
                "The student explicitly asked about eligibility/joining: state the 60% requirement and ask for their 10+2 PCM percentage as the single follow-up."
            )
        else:
            directives.append(
                "Do NOT proactively demand or ask for their board marks/percentage on this turn unless they explicitly ask if they qualify. Focus strictly on answering their question."
            )

    return "\n".join(directives)
