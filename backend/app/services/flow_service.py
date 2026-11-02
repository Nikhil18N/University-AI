"""Flow service — manages guided conversation state machines like the Admission Wizard."""

import re

WIZARD_TRIGGERS = [
    "admission wizard",
    "guided admission",
    "admission journey",
    "start wizard",
    "guide me through admission",
    "walk me through admission",
    "wizard",
]


def detect_flow_trigger(user_message: str) -> str | None:
    """Detect if the user is triggering a guided conversation flow."""
    msg = user_message.lower().strip()
    if any(t in msg for t in WIZARD_TRIGGERS):
        return "admission_wizard"
    return None


def get_wizard_step_from_history(history: list[dict[str, str]], current_message: str) -> dict | None:
    """Analyze conversation history and current message to determine Admission Wizard step."""
    # Check if a wizard was already started in recent messages
    wizard_active = False
    extracted_degree = None
    extracted_branch = None
    extracted_score = None

    full_history = history + [{"role": "user", "content": current_message}]

    # Scan history for wizard presence
    for m in full_history:
        text = m.get("content", "").lower()
        if "admission wizard" in text or "step 1 of 4" in text:
            wizard_active = True

        if any(d in text for d in ("b.tech", "btech", "m.tech", "mtech", "mba", "ph.d", "phd")):
            if "b.tech" in text or "btech" in text:
                extracted_degree = "B.Tech"
            elif "m.tech" in text or "mtech" in text:
                extracted_degree = "M.Tech"
            elif "mba" in text:
                extracted_degree = "MBA"
            elif "ph.d" in text or "phd" in text:
                extracted_degree = "Ph.D."

        if any(b in text for b in ("cse", "computer science", "ai & ml", "aiml", "ece", "data science", "electronics")):
            if "ai" in text or "aiml" in text:
                extracted_branch = "CSE (AI & ML)"
            elif "cse" in text or "computer science" in text:
                extracted_branch = "CSE (Core)"
            elif "ece" in text or "electronics" in text:
                extracted_branch = "ECE"
            elif "data science" in text:
                extracted_branch = "Data Science"

        # Check for percentages
        match = re.search(r"\b(\d{1,2}(?:\.\d+)?)\s*%", text)
        if match:
            extracted_score = match.group(0)
        elif "90%+" in text or "90% +" in text:
            extracted_score = "92%"
        elif "80%" in text:
            extracted_score = "85%"
        elif "60%" in text or "70%" in text:
            extracted_score = "68%"
        elif "below 60%" in text:
            extracted_score = "55%"

    if not wizard_active:
        return None

    # Step 4: All info collected -> Verdict
    if extracted_degree and extracted_branch and extracted_score:
        score_val = 0.0
        try:
            score_val = float(re.sub(r"[^\d.]", "", extracted_score))
        except ValueError:
            score_val = 70.0

        is_eligible = score_val >= 60.0
        return {
            "flow_name": "admission_wizard",
            "step": 4,
            "total_steps": 4,
            "step_title": "Eligibility Verdict & Next Steps",
            "degree": extracted_degree,
            "branch": extracted_branch,
            "score": extracted_score,
            "is_eligible": is_eligible,
            "completed": True,
            "options": [
                "📋 How to Apply",
                "💰 Fee Structure",
                "🏠 Hostel Details",
                "🔬 Lab Facilities",
            ],
        }

    # Step 3: Degree & Branch known -> Ask Score
    if extracted_degree and extracted_branch:
        return {
            "flow_name": "admission_wizard",
            "step": 3,
            "total_steps": 4,
            "step_title": "Qualifying Marks",
            "degree": extracted_degree,
            "branch": extracted_branch,
            "completed": False,
            "options": ["90%+ Marks", "80% - 89%", "60% - 79%", "Below 60%"],
        }

    # Step 2: Degree known -> Ask Branch
    if extracted_degree:
        return {
            "flow_name": "admission_wizard",
            "step": 2,
            "total_steps": 4,
            "step_title": "Choose Branch",
            "degree": extracted_degree,
            "completed": False,
            "options": [
                "💻 CSE (Core)",
                "🤖 CSE (AI & ML)",
                "📡 Electronics (ECE)",
                "📊 Data Science",
            ],
        }

    # Step 1: Initial step -> Ask Degree
    return {
        "flow_name": "admission_wizard",
        "step": 1,
        "total_steps": 4,
        "step_title": "Choose Degree Program",
        "completed": False,
        "options": ["🎓 B.Tech", "📘 M.Tech", "💼 MBA", "🔬 Ph.D."],
    }


def execute_wizard_step(step_info: dict) -> tuple[str, dict]:
    """Generate assistant answer and flow metadata for the current wizard step."""
    step = step_info["step"]

    if step == 1:
        text = (
            "🧭 **Welcome to the SR University Admission Wizard!** (Step 1 of 4)\n\n"
            "I'm here to guide you step-by-step through admissions, branch selection, and instant eligibility check.\n\n"
            "To begin, **what degree level are you looking for?**"
        )
    elif step == 2:
        degree = step_info.get("degree", "B.Tech")
        text = (
            f"🧭 **Step 2 of 4: Select Your Branch** ({degree})\n\n"
            f"Great choice aiming for {degree}! Which engineering or specialization track interests you the most?"
        )
    elif step == 3:
        branch = step_info.get("branch", "CSE")
        text = (
            f"🧭 **Step 3 of 4: Qualifying Percentage** ({branch})\n\n"
            f"Almost there! What was your 10+2 / Intermediate PCM aggregate percentage (or expected score)?"
        )
    else:  # step == 4
        degree = step_info.get("degree", "B.Tech")
        branch = step_info.get("branch", "CSE")
        score = step_info.get("score", "your score")
        is_eligible = step_info.get("is_eligible", True)

        if is_eligible:
            score_num = 0.0
            try:
                score_num = float(re.sub(r"[^\d.]", "", str(score)))
            except ValueError:
                score_num = 75.0

            scholarship_note = (
                "\n🌟 **Bonus:** With 90%+, you qualify for our Merit Scholarship waiver of up to 50% tuition fees!"
                if score_num >= 90.0
                else ""
            )

            text = (
                f"🎉 **Instant Admission Verdict: FULLY ELIGIBLE!** (Step 4 of 4)\n\n"
                f"With **{score}**, you comfortably meet and exceed our 60% minimum cutoff in 10+2 PCM for **{degree} {branch}**!{scholarship_note}\n\n"
                f"**Personalized Next Steps:**\n"
                f"1. **Online Application:** Visit [sru.edu.in](https://sru.edu.in) and register your basic details.\n"
                f"2. **Document Verification:** Upload your 10th and 12th marksheets.\n"
                f"3. **Seat Allocation & Offer Letter:** Receive your official branch admission letter.\n\n"
                f"What would you like to explore next about life at SR University?"
            )
        else:
            text = (
                f"📋 **Admission Assessment: Additional Guidance** (Step 4 of 4)\n\n"
                f"The standard minimum cutoff for B.Tech is 60% in 10+2 PCM. With **{score}**, direct B.Tech admission requires special academic review or alternate pathways:\n\n"
                f"• **Diploma Lateral Entry:** Join directly into 2nd year after a polytechnic diploma.\n"
                f"• **Vocational & Certificate Tracks:** Specialized technology programs at SRU.\n"
                f"• **Admissions Helpdesk:** We encourage you to speak directly with an SRU counsellor for seat guidance.\n\n"
                f"Would you like details on counsellor contacts or fee structures?"
            )

    return text, step_info
