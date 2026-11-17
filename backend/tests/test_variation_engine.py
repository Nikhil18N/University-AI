import pytest
from app.services.rag_service import extract_used_openings_and_variant, RAGService
from app.sru_agent.prompt import build_system_prompt
from app.providers.base import LLMProvider
from app.providers.embedding_base import EmbeddingProvider


class MockLLM(LLMProvider):
    async def generate(self, messages, temperature=0.7, max_tokens=None):
        return "Mock response"

    async def stream(self, messages, temperature=0.7, max_tokens=None):
        yield "Mock response"


class MockEmbedding(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 768 for _ in texts]

    async def embed_single(self, text: str) -> list[float]:
        return [0.0] * 768

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 768 for _ in texts]


def test_extract_used_openings_empty():
    variant, openings = extract_used_openings_and_variant("")
    assert variant == 1
    assert openings == "None yet (first reply in chat)"


def test_extract_used_openings_from_list():
    openings_in = [
        "Welcome to SR University!",
        "Tuition for B.Tech CSE is ₹3,40,000/yr.",
        "Hostels offer 4-sharing and 3-sharing rooms.",
    ]
    variant, openings = extract_used_openings_and_variant("", used_openings=openings_in)
    assert variant == 4  # (3 % 6) + 1 = 4
    assert '- "Welcome to SR University!"' in openings
    assert '- "Tuition for B.Tech CSE is ₹3,40,000/yr."' in openings
    assert '- "Hostels offer 4-sharing and 3-sharing rooms."' in openings


def test_extract_used_openings_rotation_modulo_6():
    for count in range(12):
        dummy_list = [f"Opening {i}" for i in range(count)]
        expected_variant = (count % 6) + 1
        variant, _ = extract_used_openings_and_variant("", used_openings=dummy_list)
        assert variant == expected_variant


def test_extract_used_openings_explicit_variant_override():
    variant, openings = extract_used_openings_and_variant(
        "", variant_id=5, used_openings=["Opening A"]
    )
    assert variant == 5
    assert '- "Opening A"' in openings


def test_extract_used_openings_from_multiline_conversation():
    conversation = (
        "user: Hello\n"
        "assistant: Welcome to SR University! How can I help you today?\n"
        "user: Tell me about CSE\n"
        "assistant: ### B.Tech CSE\n"
        "Computer Science and Engineering is our flagship branch.\n"
        "user: What about fees?\n"
        "assistant: > Note on fees\n"
        "Tuition for B.Tech CSE is ₹3,40,000 per year.\n"
    )
    variant, openings = extract_used_openings_and_variant(conversation)
    # Total assistant turns: 3 -> variant: (3 % 6) + 1 = 4
    assert variant == 4
    # First line skipped headers (###) and blockquotes (>)
    assert '- "Welcome to SR University! How can I help you today?"' in openings
    assert '- "Computer Science and Engineering is our flagship branch."' in openings
    assert '- "Tuition for B.Tech CSE is ₹3,40,000 per year."' in openings


@pytest.mark.asyncio
async def test_prepare_rag_request_renders_variant_and_openings():
    llm = MockLLM()
    embedding = MockEmbedding()
    rag = RAGService(llm, embedding)

    chunks = [
        {
            "content": "B.Tech CSE annual tuition is ₹3,40,000.",
            "metadata": {
                "document_id": "fee_schedule.pdf",
                "title": "Official Fee Schedule",
                "section": "Engineering Fees",
                "page": 1,
            },
        }
    ]

    messages, sources, evidence_text = await rag.prepare_rag_request(
        question="What is the fee for CSE?",
        conversation_context="",
        retrieved_chunks=chunks,
        variant_id=3,
        used_openings=["First greeting line."],
    )

    system_prompt = messages[0]["content"]
    assert "VARIANT_ID: 3" in system_prompt
    assert '- "First greeting line."' in system_prompt
    assert "1 = DIRECT" in system_prompt
    assert "3 = BULLETS" in system_prompt
    assert "6 = COUNSELLOR" in system_prompt
    assert "GROUNDING (never vary these)" in system_prompt


def test_build_system_prompt_agent_variation():
    profile = {"name": "Mahesh", "branch": "CSE"}
    prompt = build_system_prompt(
        profile,
        variant_id=2,
        used_openings=["Hello there!"],
    )
    assert "VARIANT_ID: 2" in prompt
    assert '- "Hello there!"' in prompt
    assert "TONE (VARIANT_ID" in prompt
    assert "2 = FRIENDLY SENIOR" in prompt
    assert "FACT LOCK" in prompt
