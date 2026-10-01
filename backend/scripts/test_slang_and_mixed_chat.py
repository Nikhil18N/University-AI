"""Test script to test spelling mistakes, shortcuts, and mixed chitchat in RAG questions.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to sys.path
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.config import settings
from app.db.session import async_session_factory
from app.providers.embedding_ollama import OllamaEmbeddingProvider
from app.providers.ollama import OllamaProvider
from app.schemas.chat import ChatRequest
from app.services.chat_service import handle_chat
from app.services.rag_service import RAGService

# Suppress noisy logs
logging.basicConfig(level=logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

TEST_SCENARIOS = [
    {
        "name": "Scenario 1: Mixed chitchat + Typos/shortcuts on Admissions & Eligibility",
        "turns": [
            "yo what's up bot! how's your day going?",
            "haha nice! my day was super hectic tbh lol... btw wht is the min elgblty for btech admsn at sru?",
            "i got 599 mrks out of 1000 in my 12th class, am i elgbl for cse or not?",
            "damn that sucks... wht abt scholrshps? if i got 920 mrks can i get any schlrshp?",
        ]
    },
    {
        "name": "Scenario 2: Slang + Mixed chatter on Placements & Packages",
        "turns": [
            "yo bro thanks for the earlier info! really helped me out",
            "btw wht is the hghest pakg in plcmnts and which compny gave it?",
            "damnn 51 lpa is crazy! wht abt avg ctc for btech?",
            "cool cool, and wht is the min cgpa rqrd to sit for plcmnts?",
        ]
    },
    {
        "name": "Scenario 3: Casual banter + Hostel rules with typos",
        "turns": [
            "lmao my roommate was making so much noise yesterday night playing games xD",
            "anyway wht is the hostle intime for 1st yr btech students?",
            "can my bro who studies in another clg stay in my hostle room for 1 nite?",
        ]
    }
]


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def run_scenario(scenario_idx: int, scenario: dict, llm, rag):
    print("=" * 80)
    print(f"RUNNING {scenario['name']}")
    print("=" * 80)
    
    session_id = f"test-slang-{scenario_idx}"
    conv_id = None
    
    for turn_idx, message in enumerate(scenario["turns"], 1):
        print(f"\n[Turn {turn_idx}] User: \"{message}\"")
        async with async_session_factory() as db:
            request = ChatRequest(
                message=message,
                session_id=session_id,
                conversation_id=conv_id,
            )
            response = await handle_chat(
                db=db,
                request=request,
                llm_provider=llm,
                rag_service=rag,
            )
            await db.commit()
            conv_id = response.conversation_id
            
            clean_ans = response.answer.encode("ascii", errors="replace").decode()
            print(f"Assistant: {clean_ans}")
            if response.sources:
                sources_str = ", ".join(f"{s.title} (p.{s.page})" for s in response.sources)
                clean_src = sources_str.encode("ascii", errors="replace").decode()
                print(f"Sources: [{clean_src}]")
            else:
                print("Sources: [None - Conversational/Guardrail]")


async def main():
    print("Initializing Ollama providers...")
    llm = OllamaProvider(
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
    )
    embedder = OllamaEmbeddingProvider(
        base_url=settings.LLM_BASE_URL,
        model=settings.EMBEDDING_MODEL,
    )
    rag = RAGService(
        llm_provider=llm,
        embedding_provider=embedder,
    )

    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        await run_scenario(i, scenario, llm, rag)


if __name__ == "__main__":
    asyncio.run(main())
