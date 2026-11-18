"""Tests for the improved quick responses and starters for SRU Buddy.

Verifies:
1. Special category fee concessions table response
2. Next-Gen Technology programs brief (AI & Robotics, Quantum AI, Precision Agriculture, Robotics & Automation)
3. Fee Structure 2027-28 directory tree and branch exploration
4. Programs available at SRU (all 6 schools + degrees)
"""
import pytest
from app.sru_agent.intents import classify_agent_intent
from app.sru_agent.agent import run_agent


@pytest.mark.asyncio
async def test_special_concessions_quick_response():
    prompt = "What are the special category fee concessions available at SR University?"
    intent = classify_agent_intent(prompt)
    assert intent == "SPECIAL_CONCESSIONS_QUERY"

    events = [e async for e in run_agent(prompt, "test-concessions-session")]
    done = [e for e in events if e["type"] == "done"][0]
    answer = done["answer"]

    # Must contain the markdown table with key categories and amounts
    assert "Special Category Fee Concessions" in answer
    assert "₹50,000 / year" in answer
    assert "Students who have lost both parents (Orphans)" in answer
    assert "Only Girl Child from Telangana" in answer
    assert "NCC 'C' Certificate holders" in answer
    assert "19 categories" in answer
    assert "| Category / Eligibility | Annual Concession |" in answer
    assert any("Calculate my fee" in s for s in done["suggestions"])


@pytest.mark.asyncio
async def test_next_gen_tech_programs_quick_response():
    prompt = "Tell me about the Next-Gen Technology programs at SR University like AI & Robotics, Quantum AI, and Precision Agriculture."
    intent = classify_agent_intent(prompt)
    assert intent == "NEXT_GEN_TECH_QUERY"

    events = [e async for e in run_agent(prompt, "test-next-gen-session")]
    done = [e for e in events if e["type"] == "done"][0]
    answer = done["answer"]

    # Must contain all 4 programs and their briefs
    assert "Artificial Intelligence & Robotics" in answer
    assert "AI & Precision Agriculture" in answer
    assert "Robotics & Automation" in answer
    assert "Quantum AI" in answer
    assert "₹4,00,000 / year" in answer
    assert "₹3,40,000 / year" in answer
    assert "SRiX" in answer
    assert any("AI & Robotics" in s for s in done["suggestions"])


@pytest.mark.asyncio
async def test_fee_structure_tree_initial():
    prompt = "What is the fee structure for 2027-28 across different programs?"
    intent = classify_agent_intent(prompt)
    assert intent == "FEE_TREE_QUERY"

    events = [e async for e in run_agent(prompt, "test-fee-tree-session")]
    done = [e for e in events if e["type"] == "done"][0]
    answer = done["answer"]

    # Must show the tree with categories
    assert "SR University Fee Structure (2027–28)" in answer
    assert "B.Tech Engineering" in answer
    assert "Management & Commerce" in answer
    assert "Agriculture" in answer
    assert "Computer Applications" in answer
    assert "B.Tech Engineering" in done["suggestions"]


@pytest.mark.asyncio
async def test_fee_structure_tree_btech_selection():
    # User selects B.Tech Engineering
    prompt = "B.Tech Engineering"
    intent = classify_agent_intent(prompt)
    assert intent == "BTECH_TREE_QUERY"

    events = [e async for e in run_agent(prompt, "test-btech-tree-session")]
    done = [e for e in events if e["type"] == "done"][0]
    answer = done["answer"]

    # Must show B.Tech branch tree
    assert "B.Tech Fee Structure (2027–28)" in answer
    assert "B.Tech CSE & Allied" in answer
    assert "B.Tech AI & Robotics" in answer
    assert "B.Tech ECE" in answer
    assert "B.Tech Core" in answer
    assert "B.Tech CSE & Allied" in done["suggestions"]


@pytest.mark.asyncio
async def test_fee_structure_btech_cse_branch():
    # User selects B.Tech CSE & Allied
    prompt = "B.Tech CSE & Allied"
    intent = classify_agent_intent(prompt)
    assert intent == "BTECH_CSE_FEE_QUERY"

    events = [e async for e in run_agent(prompt, "test-cse-fee-session")]
    done = [e for e in events if e["type"] == "done"][0]
    answer = done["answer"]

    # Detailed fee breakdown for CSE
    assert "B.Tech CSE & Allied Streams" in answer
    assert "₹1,70,000" in answer
    assert "₹3,40,000" in answer
    assert "₹5,000" in answer
    assert "₹1,85,000" in answer
    assert "Merit Scholarships" in answer
    assert "40% Waiver" in answer


@pytest.mark.asyncio
async def test_fee_structure_non_btech_management():
    # User selects Management (BBA / MBA)
    prompt = "Management (BBA / MBA)"
    intent = classify_agent_intent(prompt)
    assert intent == "MANAGEMENT_FEE_QUERY"

    events = [e async for e in run_agent(prompt, "test-mgmt-fee-session")]
    done = [e for e in events if e["type"] == "done"][0]
    answer = done["answer"]

    assert "Astra School of Business" in answer
    assert "BBA" in answer
    assert "MBA" in answer
    assert "₹1,50,000" in answer
    assert "₹3,00,000" in answer


@pytest.mark.asyncio
async def test_all_programs_quick_response():
    prompt = "What are all the programs and courses available at SR University?"
    intent = classify_agent_intent(prompt)
    assert intent == "ALL_PROGRAMS_QUERY"

    events = [e async for e in run_agent(prompt, "test-all-programs-session")]
    done = [e for e in events if e["type"] == "done"][0]
    answer = done["answer"]

    # Must list all 6 schools + degrees
    assert "School of Computer Science & Artificial Intelligence" in answer
    assert "School of Engineering" in answer
    assert "Astra School of Business" in answer
    assert "School of Agriculture" in answer
    assert "School of Design" in answer
    assert "School of Sciences & Humanities" in answer
    assert "Doctoral Studies & Research" in answer
    assert "Fee Structure 2027-28" in done["suggestions"]
