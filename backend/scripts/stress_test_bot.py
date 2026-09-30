"""Stress test script to test RAG, Companion, Hybrid, and Confusing/Trick questions.

Evaluates:
1. False premise / trick questions (e.g. 50% attendance myth, 1 lakh PhD stipend, bike inside hostel)
2. Companion + Emotional support mixed with factual university contacts (e.g. anxiety, mental health, depression)
3. Borderline policy thresholds (e.g. 71% attendance with typhoid, 5.95 CGPA for placements)
4. Contextual multi-turn follow-ups (One Student-One Job -> 2X CTC rule -> core branch exception)
5. Rules & fines (cooking in hostel room, late biometric roll call 3rd strike, visitor policy)
6. General chit-chat / companion queries
"""

import asyncio
import json
import logging
import sys
import uuid
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

# Suppress noisy logs during test run
logging.basicConfig(level=logging.WARNING)

TEST_SUITES = [
    {
        "category": "1. Emotional & Companion + University Help",
        "conversations": [
            [
                "I'm feeling really stressed, anxious and depressed about my exams. I feel like crying and don't know who to talk to on campus. Is there any help for me?",
            ],
            [
                "I have only 71% attendance in Data Structures because I was hospitalized with severe typhoid. I am terrified of getting detained. Am I definitely detained or is there any hope?",
            ]
        ]
    },
    {
        "category": "2. False Premise & Trick Questions",
        "conversations": [
            [
                "Since SR University allows 50% attendance for all engineering students, how do I apply for that relaxation?",
            ],
            [
                "Can I park my Royal Enfield bike inside the campus next to my hostel block so it is safe?",
            ],
            [
                "I heard from a friend that full-time PhD scholars get a Rs. 1,00,000 monthly fellowship. Is that true?",
            ],
            [
                "Can boys visit their female classmates inside their hostel rooms during daytime for group study?",
            ]
        ]
    },
    {
        "category": "3. Multi-Turn Follow-Ups & Context Switching",
        "conversations": [
            [
                "I am a Mechanical engineering student and I got a job offer from Cognizant for 4 LPA.",
                "Can I sit for another company now in campus placements?",
                "What if an automobile core company like Hyundai comes to campus?",
            ]
        ]
    },
    {
        "category": "4. Borderline Numbers & Fine Details",
        "conversations": [
            [
                "I have a CGPA of 5.95 and no active backlogs. Can I register for campus placements?",
            ],
            [
                "Can I cook Maggi using an electric kettle or induction stove inside my hostel room?",
            ],
            [
                "What happens if I miss the hostel biometric roll call for the 3rd time?",
            ]
        ]
    },
    {
        "category": "5. Companion & Campus Persona",
        "conversations": [
            [
                "Who is our Vice-Chancellor and does he have a nickname as a blogger in Times of India?",
            ],
            [
                "Hey buddy, what are some cool places to visit around Warangal during the weekend?",
            ]
        ]
    }
]


async def run_stress_tests():
    llm_provider = OllamaProvider(
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
    )
    embedding_provider = OllamaEmbeddingProvider(
        base_url=settings.LLM_BASE_URL,
        model=settings.EMBEDDING_MODEL,
    )
    rag_service = RAGService(llm_provider, embedding_provider)

    results = []

    print("\n" + "=" * 80)
    print("STARTING BOT STRESS TEST & CONFUSION EVALUATION")
    print("=" * 80 + "\n")

    for suite in TEST_SUITES:
        category = suite["category"]
        print(f"\n######################################################################")
        print(f"CATEGORY: {category}")
        print(f"######################################################################\n")

        for conv_idx, conv in enumerate(suite["conversations"], 1):
            session_id = f"stress-session-{uuid.uuid4().hex[:8]}"
            conversation_id = None

            print(f"\n--- Conversation #{conv_idx} ---")

            for turn_idx, user_msg in enumerate(conv, 1):
                print(f"\n[USER Turn {turn_idx}]: {user_msg}")

                req = ChatRequest(
                    message=user_msg,
                    session_id=session_id,
                    conversation_id=conversation_id,
                )

                async with async_session_factory() as db:
                    resp = await handle_chat(
                        db=db,
                        request=req,
                        llm_provider=llm_provider,
                        rag_service=rag_service,
                    )
                    conversation_id = resp.conversation_id

                clean_ans = resp.answer.encode("ascii", errors="replace").decode()
                sources_str = ", ".join(s.title for s in resp.sources) if resp.sources else "(None - Conversational/Guardrail)"

                print(f"[BOT]:\n{clean_ans}\n")
                print(f"[SOURCES]: {sources_str}")

                results.append({
                    "category": category,
                    "query": user_msg,
                    "answer": resp.answer,
                    "sources": [s.title for s in resp.sources] if resp.sources else [],
                })

    await llm_provider.close()
    await embedding_provider.close()

    # Save results to scratch json
    out_file = settings.PROJECT_ROOT / "data" / "stress_test_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Stress test completed! Results saved to {out_file}")


if __name__ == "__main__":
    asyncio.run(run_stress_tests())
