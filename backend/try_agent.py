"""Chat with the agent in your terminal, without the website.

    export GEMINI_API_KEY=your-key
    python try_agent.py
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

# Add backend directory to sys.path so app modules are resolvable
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.sru_agent.agent import run_agent


async def main():
    session = "terminal-" + uuid.uuid4().hex[:8]
    print("=" * 60)
    print("🎓 SR University (SRU) Buddy - AI Admissions Agent")
    print("   Terminal Interactive Session")
    print("   Type your query (or 'quit' to exit)")
    print("=" * 60)
    while True:
        try:
            text = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting session. Good luck with your admissions!")
            break

        if text.lower() in ("quit", "exit", "q"):
            print("Session ended. All the best!")
            break
        if not text:
            continue

        print("Agent: ", end="", flush=True)
        async for event in run_agent(text, session):
            if event["type"] == "tool" and event["status"] == "running":
                label = event.get("label", event["name"])
                print(f"\n   ⚡ [tool: {event['name']} ({label})] ", end="", flush=True)
            elif event["type"] == "tool":
                print(f"-> {event.get('result_status', 'done')}\n       ", end="", flush=True)
            elif event["type"] == "token":
                print(event["delta"], end="", flush=True)
            elif event["type"] == "error":
                print(f"\n❌ {event.get('detail', 'Error occurred')}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
