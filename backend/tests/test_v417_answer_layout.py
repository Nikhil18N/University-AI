"""v4.17.0: one answer layout for every answer (prompts/answer_layout.md).

* The layout spec is in ONE versioned file and reaches both prompts (the chat agent and system.md).
* It never carries a fee figure (fees come only from the fee engine).
* When the model's answer already contains a comparison table, the generic comparison card is not added under it.
"""
import re
import uuid

import pytest
from google.genai import types

from app.services.prompt_service import load_prompt
from app.sru_agent import memory
from app.sru_agent.agent import run_agent
from app.sru_agent.prompt import build_system_prompt


def test_layout_spec_is_one_file_used_by_both_prompts():
    layout = load_prompt("answer_layout").strip()
    assert layout.startswith("ANSWER LAYOUT")
    assert layout in build_system_prompt({})                 # the chat agent prompt ends with it
    assert layout in load_prompt("system")                   # system.md includes it ({{ANSWER_LAYOUT}})
    assert "{{ANSWER_LAYOUT}}" not in load_prompt("system")
    prompt_text = build_system_prompt({})
    assert layout in prompt_text                             # included in static prefix
    assert "CURRENT TURN CONTEXT" in prompt_text
    assert layout in prompt_text.split("CURRENT TURN CONTEXT")[0]


def test_layout_rules_cover_every_content_type():
    layout = load_prompt("answer_layout")
    for rule in ("Lead:", "3–5 bullets", "ALWAYS a Markdown table", "1. **Step:** detail", "### Title",
                 "[!NOTE]", "at most ONE short question", "50–130 words"):
        assert rule in layout, rule


def test_layout_spec_carries_no_fee_figures():
    layout = load_prompt("answer_layout")
    assert not re.search(r"₹\s?\d", layout)
    assert not re.search(r"\d,\d{2},\d{3}", layout)


def _text(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_text(text=text)]))])


class Scripted:
    def __init__(self, text):
        self.text = text
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):
        return _text(self.text)


@pytest.mark.asyncio
async def test_comparison_card_is_not_repeated_under_a_comparison_table():
    sid = f"v417l-{uuid.uuid4().hex[:10]}"
    await memory.update_profile(sid, name="Ravi Kumar", phone="9876543210", welcome_actions_shown=True)
    table = ("Core CSE keeps every software path open; AI & ML goes deeper into AI.\n\n"
             "| Aspect | CSE | CSE (AI & ML) |\n|---|---|---|\n| Focus | Broad software | AI, ML, data |\n\n"
             "Which one interests you more?")
    events = [e async for e in run_agent("compare cse and aiml", sid, client=Scripted(table), source="typed")]
    done = events[-1]
    assert done["type"] == "done" and "|---|" in done["answer"]
    assert not any(c.get("type") == "comparison" for c in done["cards"])


# ---------------------------------------------------- scores the model assumed never reach the fee engine ----
@pytest.mark.asyncio
async def test_a_score_the_student_never_gave_is_not_used_or_saved():
    from app.sru_agent import fees, tools
    sid = f"v417s-{uuid.uuid4().hex[:10]}"
    ctx = {"session_id": sid, "conversation_id": None, "profile": {}, "history": [],
           "message": "compare cse and aiml"}
    out = await tools.run_tool("compare_programs", {"program_a": "btech_cse", "program_b": "btech_ece",
                                                    "percent": 85}, ctx)
    assert all(row["scholarship_percent"] == 0 for row in out["comparison"])      # the standard fee
    fee = await tools.run_tool("calculate_fee", {"program": "btech_cse", "percent": 85}, ctx)
    assert fee["first_year_total_payable"] == fees.calculate_fee(program="btech_cse")["first_year_total_payable"]
    assert (await memory.get_profile(sid)).get("percent") is None                # nothing invented is saved


@pytest.mark.asyncio
async def test_a_score_the_student_typed_or_saved_is_used():
    from app.sru_agent import tools
    sid = f"v417s-{uuid.uuid4().hex[:10]}"
    ctx = {"session_id": sid, "conversation_id": None, "profile": {}, "history": [],
           "message": "cse fee with 85% in inter"}
    fee = await tools.run_tool("calculate_fee", {"program": "btech_cse", "percent": 85}, ctx)
    assert fee["scholarship_percent"] == 25
    ctx2 = {"session_id": sid, "conversation_id": None, "profile": {"percent": 92}, "history": [],
            "message": "and for ece?"}
    fee2 = await tools.run_tool("calculate_fee", {"program": "btech_ece", "percent": 92}, ctx2)
    assert fee2["scholarship_percent"] == 30
    elig = await tools.run_tool("check_eligibility", {"program": "btech_cse", "percent": 40},
                                {**ctx2, "message": "can i join cse?"})
    assert "40" not in str(elig.get("percent", ""))                               # the saved 92%, not 40


@pytest.mark.asyncio
async def test_standard_fee_ignores_saved_marks_and_keeps_them():
    from app.sru_agent import fees, tools
    sid = f"v417s-{uuid.uuid4().hex[:10]}"
    await memory.update_profile(sid, percent=93.1)
    ctx = {"session_id": sid, "conversation_id": None, "profile": {"percent": 93.1}, "history": [],
           "message": "standard fee of cse"}
    fee = await tools.run_tool("calculate_fee", {"program": "btech_cse", "standard_fee": True}, ctx)
    assert fee["scholarship_percent"] == 0
    assert fee["first_year_total_payable"] == fees.calculate_fee(program="btech_cse")["first_year_total_payable"]
    assert (await memory.get_profile(sid))["percent"] == 93.1                     # the saved marks stay


@pytest.mark.asyncio
async def test_placement_record_button_is_not_asked_back_as_a_topic():
    sid = f"v417p-{uuid.uuid4().hex[:10]}"
    await memory.update_profile(sid, name="Ravi Kumar", phone="9876543210", welcome_actions_shown=True)
    events = [e async for e in run_agent("Placement record", sid, source="button")]
    done = events[-1]
    assert done["type"] in ("done", "error")
    if done["type"] == "done":
        assert "What would you like to know about placements" not in done["answer"]
