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
SCORE_FRACTION_PATTERN = re.compile(r"\b(\d{2,4})\s*(?:out\s+of|/)\s*(\d{2,4})\b", re.I)


def extract_student_profile(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Scan user messages in a conversation and extract verified student profile slots."""
    profile = {
        "degree": None,
        "branch": None,
        "score_pct": None,
        "score_raw": None,
        "has_score": False,
    }

    user_texts = [m["content"] for m in messages if m.get("role") == "user"]

    for text in user_texts:
        # Check Degree
        if not profile["degree"]:
            for pattern, name in DEGREE_PATTERNS:
                if pattern.search(text):
                    profile["degree"] = name
                    break

        # Check Branch
        if not profile["branch"]:
            for pattern, name in BRANCH_PATTERNS:
                if pattern.search(text):
                    profile["branch"] = name
                    break

        # Check Score
        if not profile["has_score"]:
            pct_match = SCORE_PERCENT_PATTERN.search(text)
            if pct_match:
                try:
                    val = float(pct_match.group(1))
                    if 0 < val <= 100:
                        profile["score_pct"] = val
                        profile["score_raw"] = f"{val}%"
                        profile["has_score"] = True
                except ValueError:
                    pass

            if not profile["has_score"]:
                frac_match = SCORE_FRACTION_PATTERN.search(text)
                if frac_match:
                    try:
                        obtained = float(frac_match.group(1))
                        total = float(frac_match.group(2))
                        if total > 0 and obtained <= total:
                            pct = (obtained / total) * 100
                            profile["score_pct"] = pct
                            profile["score_raw"] = f"{obtained}/{total} ({pct:.1f}%)"
                            profile["has_score"] = True
                    except ValueError:
                        pass

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
                "CONFIRM DIRECTLY THAT THEY ARE ELIGIBLE! Never say they fall short. Share program highlights and next steps."
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
