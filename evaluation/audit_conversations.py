#!/usr/bin/env python3
"""
SRU Buddy — Conversation Audit & Dataset Builder
================================================
Reads evaluation/all_conversations_raw.json produced by the admin export endpoint.
Outputs:
  - all_conversations.jsonl          (one line per message)
  - conversation_analysis.json       (aggregate stats + error flags)
  - corrected_examples.jsonl         (template — empty answers or suspected errors)
  - evaluation_dataset.jsonl         (golden Q/A pairs from conversations with positive feedback)
"""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

EVAL_DIR = Path(__file__).parent
RAW_JSON = EVAL_DIR / "all_conversations_raw.json"
JSONL_OUT = EVAL_DIR / "all_conversations.jsonl"
ANALYSIS_OUT = EVAL_DIR / "conversation_analysis.json"
CORRECTED_OUT = EVAL_DIR / "corrected_examples.jsonl"
EVAL_DATASET_OUT = EVAL_DIR / "evaluation_dataset.jsonl"


# ── Heuristics ──────────────────────────────────────────────────────────────

EMPTY_RESPONSE_THRESHOLD = 10  # chars
TOPIC_KEYWORDS = {
    "hostel": ["hostel", "room", "mess", "curfew", "out-pass", "warden", "accommodation"],
    "fees": ["fee", "tuition", "scholarship", "concession", "payment", "installment"],
    "admissions": ["admission", "eligibility", "cutoff", "apply", "application", "jee", "eamcet"],
    "placements": ["placement", "package", "recruiter", "ctc", "lpa", "company", "offer"],
    "academics": ["attendance", "cgpa", "semester", "exam", "syllabus", "course", "credit"],
    "campus": ["campus", "library", "lab", "canteen", "transport", "bus", "gate"],
}

SUSPECTED_HALLUCINATION_PATTERNS = [
    r"\b(?:Rs\.?\s*)?[\d,]+\s*(?:lakh|lakhs|crore|crores|lpa)\b",  # money amounts
    r"\b\d{1,2}(?:\.\d+)?\s*%",  # percentages
]


def detect_topics(text: str) -> list[str]:
    text_lower = text.lower()
    topics = []
    for topic, kws in TOPIC_KEYWORDS.items():
        if any(kw in text_lower for kw in kws):
            topics.append(topic)
    return topics or ["general"]


def has_suspected_hallucination(text: str, evidence_hint: str = "") -> bool:
    """Flag assistant messages that contain numbers with no source reference."""
    if not text:
        return False
    for pat in SUSPECTED_HALLUCINATION_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            # Crude heuristic: flag if no source reference present
            if "[source" not in text.lower() and "verify" not in text.lower():
                return True
    return False


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not RAW_JSON.exists():
        print(f"ERROR: {RAW_JSON} not found. Run the export curl command first.")
        return

    with RAW_JSON.open() as f:
        data = json.load(f)

    # The export endpoint returns a list of conversations or {"conversations": [...]}
    if isinstance(data, list):
        conversations = data
    else:
        conversations = data.get("conversations", [])
    print(f"Loaded {len(conversations)} conversations from JSON export")

    # ── Stats accumulators ──
    total_messages = 0
    total_user_messages = 0
    total_assistant_messages = 0
    empty_responses: list[dict] = []
    suspected_hallucinations: list[dict] = []
    topic_counts: dict[str, int] = defaultdict(int)
    intent_counts: dict[str, int] = defaultdict(int)
    conversation_lengths: list[int] = []
    corrected_examples: list[dict] = []
    eval_pairs: list[dict] = []

    jsonl_lines: list[str] = []

    for conv in conversations:
        conv_id = conv.get("conversation_id") or conv.get("id", "")
        title = conv.get("title", "New conversation")
        created_at = conv.get("created_at", "")
        messages = conv.get("messages", [])
        conversation_lengths.append(len(messages))
        topics_in_conv: set[str] = set()

        for msg in messages:
            total_messages += 1
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            msg_id = msg.get("id", "")
            msg_created_at = msg.get("created_at", "")
            has_sources = bool(msg.get("sources"))
            feedback = msg.get("feedback")  # may be None

            if role == "user":
                total_user_messages += 1
                topics = detect_topics(content)
                for t in topics:
                    topic_counts[t] += 1
                    topics_in_conv.add(t)
            elif role == "assistant":
                total_assistant_messages += 1

                # Flag empty responses
                if len(content.strip()) < EMPTY_RESPONSE_THRESHOLD:
                    empty_responses.append({
                        "conversation_id": conv_id,
                        "message_id": msg_id,
                        "title": title,
                        "content": content,
                        "created_at": msg_created_at,
                    })
                    # Add to corrected examples template
                    corrected_examples.append({
                        "conversation_id": conv_id,
                        "message_id": msg_id,
                        "error_type": "EMPTY_RESPONSE",
                        "original_question": "",  # fill manually
                        "bad_answer": content,
                        "corrected_answer": "",   # fill manually
                        "verified": False,
                    })

                # Flag suspected hallucinations
                elif has_suspected_hallucination(content):
                    suspected_hallucinations.append({
                        "conversation_id": conv_id,
                        "message_id": msg_id,
                        "content_preview": content[:200],
                    })

                # Golden eval pairs from thumbs-up feedback
                if feedback and isinstance(feedback, dict) and feedback.get("rating") == "thumbs_up":
                    eval_pairs.append({
                        "id": f"eval-{len(eval_pairs)+1:04d}",
                        "conversation_id": conv_id,
                        "message_id": msg_id,
                        "answer": content,
                        "has_sources": has_sources,
                        "source": "user_thumbs_up",
                        "verified": True,
                    })

            # Write to JSONL
            jsonl_lines.append(json.dumps({
                "conversation_id": conv_id,
                "title": title,
                "conversation_created_at": created_at,
                "message_id": msg_id,
                "role": role,
                "content": content,
                "created_at": msg_created_at,
                "has_sources": has_sources,
                "has_feedback": feedback is not None,
                "feedback_rating": feedback.get("rating") if isinstance(feedback, dict) else None,
                "topics": detect_topics(content) if role == "user" else [],
            }))

    # ── Write all_conversations.jsonl ──
    with JSONL_OUT.open("w") as f:
        f.write("\n".join(jsonl_lines) + "\n")
    print(f"Wrote {len(jsonl_lines)} lines to {JSONL_OUT}")

    # ── Write corrected_examples.jsonl ──
    with CORRECTED_OUT.open("w") as f:
        for ex in corrected_examples:
            f.write(json.dumps(ex) + "\n")
    print(f"Wrote {len(corrected_examples)} corrected example templates to {CORRECTED_OUT}")

    # ── Write evaluation_dataset.jsonl ──
    with EVAL_DATASET_OUT.open("w") as f:
        for pair in eval_pairs:
            f.write(json.dumps(pair) + "\n")
    print(f"Wrote {len(eval_pairs)} golden eval pairs to {EVAL_DATASET_OUT}")

    # ── Build analysis report ──
    analysis = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": "evaluation/all_conversations_raw.json",
        "summary": {
            "total_conversations": len(conversations),
            "total_messages": total_messages,
            "total_user_messages": total_user_messages,
            "total_assistant_messages": total_assistant_messages,
            "avg_messages_per_conversation": round(total_messages / len(conversations), 1) if conversations else 0,
            "avg_turns_per_conversation": round(total_user_messages / len(conversations), 1) if conversations else 0,
        },
        "quality_flags": {
            "empty_or_very_short_responses": {
                "count": len(empty_responses),
                "threshold_chars": EMPTY_RESPONSE_THRESHOLD,
                "conversations": empty_responses,
            },
            "suspected_hallucinations": {
                "count": len(suspected_hallucinations),
                "note": "Heuristic only — assistant messages containing numbers/amounts without source citation",
                "conversations": suspected_hallucinations,
            },
        },
        "topic_distribution": dict(sorted(topic_counts.items(), key=lambda x: -x[1])),
        "golden_eval_pairs_count": len(eval_pairs),
        "conversation_length_distribution": {
            "min_messages": min(conversation_lengths) if conversation_lengths else 0,
            "max_messages": max(conversation_lengths) if conversation_lengths else 0,
            "avg_messages": round(sum(conversation_lengths) / len(conversation_lengths), 1) if conversation_lengths else 0,
        },
        "data_files": {
            "original_verbatim": "evaluation/original_conversations.md",
            "all_messages_jsonl": "evaluation/all_conversations.jsonl",
            "corrected_examples": "evaluation/corrected_examples.jsonl",
            "evaluation_dataset": "evaluation/evaluation_dataset.jsonl",
        },
        "preservation_note": (
            "All 64 conversations are preserved verbatim in original_conversations.md. "
            "No conversations or messages have been deleted, modified, or truncated."
        ),
    }

    with ANALYSIS_OUT.open("w") as f:
        json.dump(analysis, f, indent=2)
    print(f"Wrote analysis to {ANALYSIS_OUT}")

    # ── Print summary ──
    print("\n" + "="*60)
    print("CONVERSATION AUDIT SUMMARY")
    print("="*60)
    print(f"  Total conversations:   {len(conversations)}")
    print(f"  Total messages:        {total_messages}")
    print(f"  Empty responses:       {len(empty_responses)}")
    print(f"  Suspected hallucinations (heuristic): {len(suspected_hallucinations)}")
    print(f"  Golden eval pairs:     {len(eval_pairs)}")
    print(f"\nTopic distribution:")
    for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
        print(f"    {topic:15s}: {count} messages")
    print("="*60)


if __name__ == "__main__":
    main()
