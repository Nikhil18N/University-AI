"""Script to enrich data/SRU Agentic AI.docx with verified university facts.

Adds verified answers in their correct sections:
- Programs > Eligibility (60% cutoff, 1000 total marks default, 599/1000 is 59.9%, no entrance exam for direct/management quota, diploma lateral entry, MBA/M.Tech 60%)
- Fee > Fee (National) & Fee (International) (CSE 2,10,000 + other fees, other branches 20k-30k less, paid semester-wise)
- Scholarship (Merit on 12th marks: 970+ gets 30%, 900-969 gets 20%, first come first served)
- Placements (51 LPA highest Microsoft, 6 LPA average, eligibility 7.5 CGPA and no backlogs)
"""

import shutil
from pathlib import Path
import docx

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOCX_PATH = PROJECT_ROOT / "data" / "SRU Agentic AI.docx"
BACKUP_PATH = PROJECT_ROOT / "data" / "SRU Agentic AI.docx.bak"

# Section-scoped Q&A updates
SECTION_UPDATES = {
    "Scholarship": {
        "Am I eligible for a scholarship?": (
            "Yes! Merit scholarships at SR University are awarded based on 12th / Intermediate marks on a first-come, first-served basis:\n"
            "• Students scoring 970 out of 1000 marks and above (97%+) can receive up to a 30% scholarship.\n"
            "• Students scoring above 900 and below 970 marks (90% to 96.9%) can receive up to a 20% scholarship."
        ),
        "Is the scholarship application open?": (
            "Yes, scholarship applications are open. Merit scholarships are allocated on a first-come, first-served basis "
            "based on 12th marks (970+ gets up to 30%, 900-969 gets up to 20%), so early applicants have priority."
        ),
        "What is the last date to apply?": (
            "Merit scholarships are distributed on a first-come, first-served basis according to availability in each scholarship slab. "
            "Students are strongly advised to apply as early as possible before scholarship seats are filled."
        ),
    },
    "Placements": {
        "What is the highest package?": (
            "The highest placement package at SR University is 51 LPA (Lakhs Per Annum), offered by Microsoft."
        ),
        "What is the average package?": (
            "The average placement package across graduating students is 6 LPA."
        ),
        "Who is eligible for the top recruiters drive?": (
            "To be eligible for campus placement drives with top recruiters, students must maintain a minimum CGPA of 7.5 and above with no active backlogs."
        ),
        "Which companies recruit students?": (
            "Top recruiting companies include Microsoft (which offered the highest package of 51 LPA), along with prominent multinational IT "
            "and engineering companies across software, product development, and core industries."
        ),
    },
    "Fee": {
        "What is the fee for B.Tech Computer Science?": (
            "The annual tuition fee for B.Tech Computer Science & Engineering (CSE) is Rs. 2,10,000 plus other applicable university fees. "
            "The fee is payable semester-wise (half of the annual amount, i.e., Rs. 1,05,000, per semester plus other fees)."
        ),
        "What is the fee for an MBA?": (
            "The annual fee for other programs is typically Rs. 20,000 to Rs. 30,000 lower than B.Tech CSE, payable per semester."
        ),
        "Can I pay in installments?": (
            "Yes, the fee is paid on a semester basis (half of the annual tuition fee is paid each semester along with other applicable fees)."
        ),
        "How much fee do I need to pay?": (
            "The annual tuition fee for B.Tech CSE is Rs. 2,10,000 plus other fees. For other engineering branches, "
            "it is Rs. 20,000 to Rs. 30,000 lower (around Rs. 1,80,000 to Rs. 1,90,000 per year). "
            "Payment is made each semester (half the annual fee per semester plus other fees)."
        ),
    },
    "Programs": {
        "What is the eligibility for B.Tech CSE?": (
            "Candidates must have passed 10+2 / Intermediate with Mathematics, Physics, and Chemistry (MPC) "
            "and secured a minimum of 60% aggregate marks (calculated based on marks obtained out of total marks, "
            "default 1000 marks in state boards). For direct or management quota admission, no entrance exam marks or rank are required."
        ),
        "What minimum percentage is required?": (
            "A minimum of 60% aggregate marks in 12th / Intermediate is required for admission. "
            "The percentage is calculated based on the student's total marks out of total maximum marks "
            "(default total marks is 1000 for state boards, though other state or central boards may differ). "
            "This 60% eligibility applies across all branches for both regular and direct/management quota admissions."
        ),
        "Can diploma students apply?": (
            "Yes, diploma (polytechnic) holders are eligible to apply for direct second-year lateral entry into B.Tech programs."
        ),
        "Who can apply for an MBA?": (
            "Candidates holding any recognized bachelor's degree with a minimum of 60% aggregate marks are eligible to apply for the MBA program."
        ),
        "What are the eligibility criteria for M.Tech?": (
            "Applicants must possess a relevant B.Tech / B.E. degree with a minimum of 60% aggregate marks."
        ),
        "Am I eligible for this course?": (
            "Admission eligibility requires a minimum of 60% aggregate marks in your qualifying exam (12th / Intermediate for UG, "
            "or Bachelor's degree for PG), calculated based on your total marks out of maximum marks (default 1000 in state boards). "
            "This applies to all branches. For direct / management quota admission, no entrance exam is required."
        ),
    },
}

EXTRA_ELIGIBILITY_QA = [
    (
        "Is it 60% and above?",
        "Yes, the required eligibility for admission is 60% and above aggregate marks in 12th / Intermediate. "
        "The percentage is calculated based on marks obtained out of total marks (default total marks is 1000 in state boards). "
        "This 60% requirement applies to all branches, including CSE, for both regular and direct/management quota admissions."
    ),
    (
        "I got 599 out of 1000 marks in my 12th class, so am I eligible to get admission?",
        "With 599 out of 1000 marks in your 12th class, your score is 59.9%, which is just 1 mark below the university's "
        "standard minimum cutoff of 60% (600/1000). The official eligibility requirement is 60%. Because your score of 59.9% "
        "is right at the threshold, you should contact the SR University admissions office directly at 833 100 3030 or 4040 "
        "to find out if direct / management quota admission or discretionary evaluation is possible in your case."
    ),
    (
        "Is an entrance exam required for direct or management quota admission?",
        "No, entrance exam marks or rank (such as TG EAPCET or JEE Main) are not required for direct or management quota admissions. "
        "Direct admission is granted strictly based on meeting the 12th / Intermediate marks criteria (minimum 60%)."
    ),
    (
        "What is required eligibility to get a admission?",
        "To get admission at SR University, the required eligibility is a minimum of 60% aggregate marks in 12th / Intermediate "
        "(or equivalent qualifying examination). Percentage is calculated on the candidate's marks out of total marks (default 1000 marks "
        "in state boards, though other boards may differ). This 60% criteria applies to all branches for both regular and direct/management "
        "quota admissions. Entrance exams are not required for direct/management quota admissions."
    ),
]


def enrich_docx():
    if not BACKUP_PATH.exists():
        raise FileNotFoundError(f"Backup DOCX not found at {BACKUP_PATH}")

    # Always restore fresh from backup
    shutil.copy2(BACKUP_PATH, DOCX_PATH)
    print(f"Restored clean DOCX from backup: {BACKUP_PATH}")

    doc = docx.Document(str(DOCX_PATH))
    current_section = "General"
    inserted_count = 0

    i = 0
    while i < len(doc.paragraphs):
        p = doc.paragraphs[i]
        txt = p.text.strip()
        if not txt:
            i += 1
            continue

        if p.style.name == "Title":
            current_section = txt
            i += 1
            continue

        sec_updates = SECTION_UPDATES.get(current_section, {})
        matched_q = None
        for q in sec_updates:
            if q.lower() == txt.lower():
                matched_q = q
                break

        if matched_q:
            # Set question bold
            for r in p.runs:
                r.bold = True
            ans_text = sec_updates[matched_q]

            # Insert answer paragraph immediately after question
            p_elem = p._p
            new_p = doc.add_paragraph()
            r_ans = new_p.add_run(ans_text)
            r_ans.bold = False
            p_elem.addnext(new_p._p)
            last_elem = new_p._p
            inserted_count += 1
            print(f"  [{current_section}] Inserted answer for: '{matched_q}'")

            # If this is the percentage question in Programs, append the extra Q&A blocks
            if current_section == "Programs" and matched_q == "What minimum percentage is required?":
                for extra_q, extra_a in EXTRA_ELIGIBILITY_QA:
                    q_para = doc.add_paragraph()
                    q_run = q_para.add_run(extra_q)
                    q_run.bold = True
                    last_elem.addnext(q_para._p)
                    last_elem = q_para._p

                    a_para = doc.add_paragraph()
                    a_run = a_para.add_run(extra_a)
                    a_run.bold = False
                    last_elem.addnext(a_para._p)
                    last_elem = a_para._p
                    inserted_count += 1
                    print(f"  [{current_section}] Inserted extra Q&A: '{extra_q}'")

        i += 1

    doc.save(str(DOCX_PATH))
    print(f"\n[OK] Successfully enriched DOCX at {DOCX_PATH} with {inserted_count} Q&A items.")


if __name__ == "__main__":
    enrich_docx()
