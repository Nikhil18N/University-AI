"""Fee enquiries: collect the details a correct fee needs BEFORE calculating it.

A personal fee depends on the programme and branch, the board (Telangana / AP State Board, CBSE,
ICSE or IB), the 10+2 marks and, for B.Tech and B.Sc Agriculture, a JEE Main percentile or
TG / AP EAPCET rank. SR University has one campus (Warangal), so the campus is never asked.

decide() looks at the message, what the chat already knows and what was asked before, and says:
    {"action": "ask", "text": ..., "chips": [...], "state": {...}}   ask (no AI call: instant)
    {"action": "calculate", "args": {...}}                           all details known
    None                                                             not a fee enquiry
Questions are asked at most once each, so a student is never stuck in a loop.
"""
import re

from . import config, fees

FEE_PORTAL_URL = config.FEE_PORTAL_URL

_FEE_WORDS = re.compile(r"\b(?:fee|fees|fess|feez|tuition|cost|costs|schol\w*|how\s+much|per\s+sem\w*|payable|"
                        r"calculate|calculation|estimate)\b", re.IGNORECASE)
# Fee questions that are not about a programme's tuition (other tools answer these).
_OTHER_FEE_TOPIC = re.compile(
    r"\b(?:hostel|mess|bus|transport|application\s+fee|form\s+fee|pay(?:ment)?s?\b|paid|refund\w*|instal\w*|emi|"
    r"loan|concession\w*|sibling|sports|defen[cs]e|single\s+parent|orphan|girl|disab\w*|vs|versus|compare|"
    r"comparison|difference|cheaper|cheapest|last\s+date|due\s+date|deadline|exam\s+fee|caution|deposit)\b",
    re.IGNORECASE)
_STATE_BOARD = re.compile(
    r"\b(?:state\s*board|bie(?:ap|ts)?|board\s+of\s+intermediate|intermediate\s+board|inter\s+board|"
    r"(?:ts|tg|ap|telangana|andhra(?:\s+pradesh)?)\s*(?:state\s*)?(?:board|inter(?:mediate)?))\b", re.IGNORECASE)
_CBSE = re.compile(r"\bcbse\b", re.IGNORECASE)
_ICSE = re.compile(r"\b(?:icse|isc)\b", re.IGNORECASE)
_IB = re.compile(r"\b(?:ib|international\s+baccalaureate)\b", re.IGNORECASE)
_SCORE_WORDS = r"(?:eapcet|eamcet|emcet|emact|eamect|eamcent|ts\s*eapcet|ap\s*eapcet|tg\s*eapcet)"
_NO_ENTRANCE = re.compile(
    r"\b(?:no|not|didn'?t|did\s+not|haven'?t|have\s+not|never|without)\b[^.?!]{0,30}\b(?:jee|eapcet|eamcet|entrance|"
    r"rank|percentile)\b|\bno\s+(?:entrance|exam|jee|eapcet|eamcet)\b|\b(?:only|just)\s+(?:my\s+)?(?:inter|board|"
    r"12th|marks|percentage)\b|^\s*(?:no|nope|none|nothing|na|n/a|not\s+yet)\s*[.!]?\s*$", re.IGNORECASE)
_STANDARD_ONLY = re.compile(
    r"\b(?:standard|base|basic|normal|general|full)\s+fee|\bwithout\s+(?:any\s+)?scholarship|\bno\s+scholarship|"
    r"\bjust\s+(?:show\s+)?(?:the\s+)?(?:fee|fees|standard)\b|\bskip\b(?!\s*,?\s*use\s+my)", re.IGNORECASE)
_BOARD_LABEL = {"state_board": "Telangana / AP State Board", "cbse": "CBSE / ICSE", "ib": "IB"}
_ENTRANCE_PROGRAMS = ("btech_", "bsc_agri")  # where JEE Main / EAPCET is usual


def parse_details(message: str) -> dict:
    """Everything fee-relevant the student typed in this one message."""
    low = (message or "").lower()
    out: dict = {}
    if fees.find_program(message or ""):
        out["program"] = message
    elif fees._is_generic_btech(low) or re.search(r"\b(?:b\.?\s?tech|btech|engineering)\b", low):
        out["generic_btech"] = True
    if _IB.search(message or ""):
        out["board"] = "ib"
    elif _CBSE.search(message or "") or _ICSE.search(message or ""):
        out["board"] = "cbse"
        out["board_label"] = "ICSE" if _ICSE.search(message or "") and not _CBSE.search(message or "") else "CBSE"
    elif _STATE_BOARD.search(message or ""):
        out["board"] = "state_board"
    m = re.search(r"(?<![\d.])(\d{2}(?:\.\d+)?)\s*(?:%|percent|per\s*cent|percentage)", low)
    marks = re.search(r"(?<!\d)(\d{3,4})\s*(?:marks|/\s*1000|out\s+of\s+1000)", low)
    if m and float(m.group(1)) <= 100:
        out["percent"] = float(m.group(1))
    elif marks and int(marks.group(1)) <= 1000:
        out["percent"] = round(int(marks.group(1)) / 10, 2)
    m = re.search(rf"\b{_SCORE_WORDS}\b\D{{0,25}}(\d[\d,]{{0,6}})\b|\brank\D{{0,12}}(\d[\d,]{{0,6}})\b"
                  rf"|(\d[\d,]{{0,6}})\s*(?:{_SCORE_WORDS}\s*)?(?:rank|in\s+{_SCORE_WORDS})\b"
                  rf"|\b(\d{{1,3}})\s*k\s*(?:{_SCORE_WORDS}\s*)?rank\b", low)
    if m:
        if m.group(4):
            out["eapcet_rank"] = int(m.group(4)) * 1000
        else:
            out["eapcet_rank"] = int((m.group(1) or m.group(2) or m.group(3)).replace(",", ""))
    m = re.search(r"\bjee\D{0,25}(\d{1,2}(?:\.\d+)?)\b|(\d{1,2}(?:\.\d+)?)\s*(?:percentile|%ile)", low)
    if m:
        out["jee_percentile"] = float(m.group(1) or m.group(2))
    m = re.search(r"\bib\D{0,15}(\d{2})\b|(?<!\d)(\d{2})\s*(?:/\s*45|points|out\s+of\s+45)", low)
    if m and 0 < int(m.group(1) or m.group(2)) <= 45:
        out["ib_score"] = int(m.group(1) or m.group(2))
        out["board"] = "ib"
    if _NO_ENTRANCE.search(message or ""):
        out["no_entrance"] = True
    if _STANDARD_ONLY.search(message or ""):
        out["standard_only"] = True
    if re.search(r"\bskip\b|\buse\s+(?:my|the)\s+rank\b|\bdon'?t\s+(?:know|remember)\b|\bnot\s+sure\b|"
                 r"\bcalculate\s+(?:it\s+)?(?:now|anyway)\b|\bthat'?s\s+all\b", message or "", re.IGNORECASE):
        out["skip"] = True
    return out


def _bare_number(message: str):
    m = re.fullmatch(r"\s*(\d{1,6}(?:\.\d+)?)\s*%?\s*", message or "")
    return float(m.group(1)) if m else None


def is_fee_enquiry(message: str) -> bool:
    return bool(_FEE_WORDS.search(message or "")) and not _OTHER_FEE_TOPIC.search(message or "")


def _btech_branches_text() -> str:
    data = fees.load_data()["programs"]
    seen, lines = set(), []
    for key, prog in data.items():
        if not key.startswith("btech_"):
            continue
        fee = prog["tuition_per_year"]
        name = prog["name"].split(" (")[0]
        if (name, fee) in seen:
            continue
        seen.add((name, fee))
        lines.append(f"- {name}: {fees.inr(fee)} per year")
    return "\n".join(lines)


def _scores_list(prog_key: str, level: str, board_known: bool) -> str:
    if level == "pg":
        return "- Your percentage in the qualifying degree (for example B.Tech, B.Sc or BBA)"
    items = []
    if not board_known:
        items.append("- Your board: Telangana / AP State Board, CBSE, ICSE or IB")
    items.append("- Your Intermediate / 12th marks (percentage, or marks out of 1000; IB: points out of 45)")
    if prog_key.startswith(_ENTRANCE_PROGRAMS):
        items.append("- Your JEE Main percentile or TG / AP EAPCET rank, if you have one (a good score can "
                     "give a higher scholarship)")
    return "\n".join(items)


def decide(message: str, profile: dict, intake: dict | None) -> dict | None:
    """What to do with a fee enquiry. `intake` is what this chat collected and asked before."""
    intake = dict(intake or {})
    said = parse_details(message)
    active = bool(intake) and int(intake.get("turns", 0)) < 4
    number = _bare_number(message)
    if not is_fee_enquiry(message):
        # Only a reply to our own question continues the intake (a number, a board, "no JEE"...).
        reply_like = bool(said.keys() - {"generic_btech"}) or number is not None
        if not (active and reply_like):
            return None
    if active and number is not None:
        # A bare number answers the question we asked last.
        waiting = intake.get("waiting_for")
        if waiting == "rank":
            said.setdefault("eapcet_rank" if number > 100 else "jee_percentile",
                            int(number) if number > 100 else number)
        elif waiting == "ib" and number <= 45:
            said.setdefault("ib_score", int(number))
        elif 35 <= number <= 100:
            said.setdefault("percent", number)
        elif 100 < number <= 1000:
            said.setdefault("percent", round(number / 10, 2))
        elif number > 1000:
            said.setdefault("eapcet_rank", int(number))

    # What we know: the student's profile, then this chat's answers, then this message.
    known = {k: profile.get(k) for k in ("percent", "board", "eapcet_rank", "jee_percentile", "ib_score")
             if profile.get(k) not in (None, "")}
    known.update({k: v for k, v in intake.items() if k in (
        "program", "percent", "board", "board_label", "eapcet_rank", "jee_percentile", "ib_score", "no_entrance")})
    known.update({k: v for k, v in said.items() if k != "generic_btech"})
    if said.get("program"):
        known["program"] = said["program"]
    elif not known.get("program") and profile.get("program_interest") and not said.get("generic_btech"):
        known["program"] = profile["program_interest"]
    asked = set(intake.get("asked", []))
    state = {**{k: v for k, v in known.items() if k != "standard_only"}, "asked": sorted(asked),
             "turns": int(intake.get("turns", 0)) + 1}

    prog_key = fees.find_program(str(known.get("program") or ""))
    portal = f"You can also check it on the official calculator: {FEE_PORTAL_URL}"

    # 1. Which programme / branch?
    if not prog_key:
        if "program" in asked:
            return None  # asked once already; let the model help in its own words
        state["asked"] = sorted(asked | {"program"})
        state["waiting_for"] = "program"
        if said.get("generic_btech") or fees._is_generic_btech(message.lower()):
            text = ("B.Tech fees depend on the branch. The {year} standard tuition (before any scholarship, as per "
                    "the Admissions Office) is:\n{branches}\n\nWhich branch are you interested in? Tell me your "
                    "board, Intermediate / 12th marks and JEE Main or EAPCET score too, and I will work out your "
                    "scholarship and exact fee.").format(year=config.ADMISSION_YEAR, branches=_btech_branches_text())
            chips = ["B.Tech CSE", "B.Tech AI and Robotics", "B.Tech ECE", "B.Tech Mechanical"]
        else:
            text = ("Sure, I can work out the exact fee and scholarship for you. Which programme are you interested "
                    "in? For example B.Tech CSE, B.Tech ECE, B.Sc Agriculture, BBA, B.Des or MBA (for B.Tech, "
                    "please mention the branch).")
            chips = ["B.Tech CSE", "B.Tech ECE", "BBA", "MBA"]
        return {"action": "ask", "text": text, "chips": chips, "state": state}

    known["program"] = prog_key  # store the course itself, not the whole sentence
    state["program"] = prog_key
    prog = fees.load_data()["programs"][prog_key]
    level = prog.get("level", "ug")
    name = prog["name"]
    standard = (f"The {config.ADMISSION_YEAR} standard tuition for **{name}** is **{fees.inr(prog['tuition_per_year'])} "
                f"per year** ({fees.inr(prog['tuition_per_year'] // 2)} per semester), before any scholarship, as "
                f"per the Admissions Office.")
    has_score = any(known.get(k) not in (None, "") for k in ("percent", "eapcet_rank", "jee_percentile", "ib_score"))

    def calculate():
        args = {"program": str(known["program"])}
        for k in ("percent", "eapcet_rank", "jee_percentile", "ib_score"):
            if known.get(k) not in (None, ""):
                args[k] = known[k]
        if known.get("board") in ("cbse", "state_board", "ib") and level != "pg":
            args["board"] = "cbse" if known["board"] == "cbse" else "state_board"
        return {"action": "calculate", "args": args, "state": None,
                "details": {"board": _BOARD_LABEL.get(known.get("board") or "", ""),
                            "board_label": known.get("board_label"), "no_entrance": known.get("no_entrance")}}

    # 2. "Just the standard fee" / "skip, use what I gave"
    if (said.get("standard_only") and not has_score) or said.get("skip"):
        return calculate()

    # 3. IB students need their IB points, not a percentage
    if level != "pg" and known.get("board") == "ib" and not known.get("ib_score") and "ib" not in asked:
        state["asked"] = sorted(asked | {"ib"})
        state["waiting_for"] = "ib"
        return {"action": "ask", "text": "Thanks. What is your IB Diploma score (points out of 45)? The IB "
                "scholarship slabs use points, not a percentage.", "chips": ["30", "34", "38"], "state": state}

    # 4. No marks or scores yet: give the standard fee and ask for everything in ONE message
    if not has_score:
        if "scores" in asked:
            return calculate()  # asked once; show the standard fee rather than ask again
        state["asked"] = sorted(asked | {"scores", "entrance"})
        state["waiting_for"] = "ib" if known.get("board") == "ib" else "percent"
        text = (f"{standard}\n\nTo work out your scholarship and the exact amount you pay, please tell me:\n"
                f"{_scores_list(prog_key, level, bool(known.get('board')))}\n\n{portal}")
        chips = (["My degree % is 75", "Just the standard fee"] if level == "pg" else
                 ["State Board, 85%", "CBSE, 90%", "EAPCET rank 15000", "Just the standard fee"])
        return {"action": "ask", "text": text, "chips": chips, "state": state}

    # 4b. Only an entrance score: the board marks may give a bigger scholarship
    if (level != "pg" and known.get("percent") is None and not known.get("ib_score")
            and "marks" not in asked and "scores" not in asked):
        state["asked"] = sorted(asked | {"marks"})
        state["waiting_for"] = "percent"
        return {"action": "ask", "chips": ["State Board, 85%", "CBSE, 90%", "Skip, use my rank"], "state": state,
                "text": ("Thanks. What were your Intermediate / 12th marks, and which board (Telangana / AP State "
                         "Board, CBSE, ICSE or IB)? Board marks can earn a scholarship too, and the best one is "
                         "applied.")}

    # 5. The board changes the scholarship only for some percentages: ask only then
    pct = known.get("percent")
    if level != "pg" and pct is not None and not known.get("board") and "board" not in asked:
        as_state = fees.scholarship_for(prog_key, percent=pct, board="state_board")["percent"]
        as_cbse = fees.scholarship_for(prog_key, percent=pct, board="cbse")["percent"]
        if as_state != as_cbse:
            state["asked"] = sorted(asked | {"board"})
            state["waiting_for"] = "board"
            return {"action": "ask", "chips": ["Telangana State Board", "AP State Board", "CBSE", "ICSE"],
                    "state": state,
                    "text": (f"Which board did you study under? With {pct:g}% the scholarship is "
                             f"{as_state}% for Telangana / AP State Board and {as_cbse}% for CBSE / ICSE, so it "
                             f"matters for your fee.")}

    # 6. B.Tech / B.Sc Agriculture: an entrance score may give more; ask once
    if (level != "pg" and prog_key.startswith(_ENTRANCE_PROGRAMS) and "entrance" not in asked
            and not known.get("no_entrance") and not known.get("eapcet_rank") and not known.get("jee_percentile")):
        board = "cbse" if known.get("board") == "cbse" else "state_board"
        best = fees.scholarship_for(prog_key, percent=pct, board=board, ib_score=known.get("ib_score"))["percent"]
        if best < 40:
            state["asked"] = sorted(asked | {"entrance"})
            state["waiting_for"] = "rank"
            return {"action": "ask", "chips": ["No entrance exam", "EAPCET rank 12000", "JEE 85 percentile"],
                    "state": state,
                    "text": (f"Got it. Did you also write JEE Main or TG / AP EAPCET? Your marks give a {best}% "
                             f"scholarship; a JEE Main percentile of 80+ or an EAPCET rank up to 20,000 can give "
                             f"more, and the best one is applied. Share your score, or say \"no entrance exam\".")}

    return calculate()
