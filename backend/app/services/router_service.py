"""Query router service — classifies and decomposes messages into typed sub-questions with interest extraction."""

import json
import logging
import re
from typing import Any

from app.providers.base import LLMProvider
from app.services.prompt_service import render_prompt

logger = logging.getLogger(__name__)

VALID_TYPES = {"factual", "persuasive", "chitchat", "sensitive", "out_of_scope"}

# Comprehensive multi-lingual crisis, distress, self-harm and sensitive keywords (T8)
CRISIS_DISTRESS_REGEX = re.compile(
    r"\b("
    # English
    r"suicide|kill\s+myself|end\s+my\s+life|ending\s+it\s+all|don't\s+want\s+to\s+live|"
    r"want\s+to\s+die|feel(?:ing)?\s+hopeless|hopeless|lost\s+all\s+hope|no\s+reason\s+to\s+live|"
    r"give\s+up\s+on\s+life|hate\s+my\s+life|better\s+off\s+dead|harm\s+myself|cut\s+myself|"
    # Telugu-English
    r"asha\s+ledu|aasha\s+ledu|pranam\s+theesukunta|praanam\s+theesukunta|jeevitham\s+meeda\s+virakthi|"
    r"jeevitham\s+meeda\s+asha\s+poindi|chasthe\s+bagunnu|chaavali\s+anipistundi|bathakali\s+ani\s+ledu|"
    r"inka\s+bathakadam\s+enduku|chachi\s+pothanu|"
    # Hinglish
    r"koi\s+umeed\s+nahi|koyi\s+ummeed\s+nahi|marne\s+ka\s+mann\s+kar\s+raha|mar\s+jana\s+chahta\s+hu|"
    r"sab\s+khatam\s+ho\s+gaya|sab\s+khatam\s+karna\s+chahta\s+hu|zindagi\s+se\s+tang\s+aa\s+gaya|"
    r"jeene\s+ki\s+chahat\s+nahi|khudkhushi|jaan\s+de\s+dunga|"
    # High-risk sensitive admissions traps
    r"guarantee\b.*?\b(admission|placement|job|seat|scholarship|20\s+lpa)|my\s+otp\s+is\b"
    r")\b",
    re.IGNORECASE,
)


def is_crisis_or_distress(text: str) -> bool:
    """Fast-path deterministic check for mental health distress, crisis, or high-risk sensitive turns."""
    if not text:
        return False
    return bool(CRISIS_DISTRESS_REGEX.search(text))


# Fast pre-classification patterns for instantaneous sub-10ms routing on common conversational openers
FAST_ROUTER_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^\s*(hi|hello|hey|good\s+(morning|afternoon|evening)|howdy)(\s+(there|buddy|friend|assistant|bot|sru|all))?[!.,\s]*$", re.I), "chitchat"),
    (re.compile(r"^\s*(ok|okay|k|cool|got\s+it|understood|great|awesome|sure|thanks|thank\s+you)(\s+(a\s+lot|so\s+much|buddy|bro))?[!.,\s]*$", re.I), "chitchat"),
    (re.compile(r"^\s*(who\s+won|weather|election|cricket\s+score|write\s+my\s+assignment|hack\b)[^?]*\??$", re.I), "out_of_scope"),
]


def _clean_json_output(text: str) -> str:
    """Extract JSON object from markdown code fences or raw string."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


async def route_and_decompose_message(
    llm: LLMProvider,
    message: str,
    conversation_context: str = "",
) -> dict[str, Any]:
    """Decompose message into typed parts and extract student interests.

    Returns:
        {
            "parts": [{"text": str, "type": str}],
            "interests": [str]
        }
    """
    clean_msg = message.strip()
    if not clean_msg:
        return {"parts": [{"text": message, "type": "chitchat"}], "interests": []}

    # Fast-path Layer 1: Instant deterministic crisis/distress routing (< 2ms)
    if is_crisis_or_distress(clean_msg):
        logger.info("Fast-path crisis/distress detected; immediate sensitive routing: %s", clean_msg[:60])
        return {"parts": [{"text": clean_msg, "type": "sensitive"}], "interests": []}

    # Fast pattern match for short obvious queries
    for pattern, part_type in FAST_ROUTER_PATTERNS:
        if pattern.search(clean_msg):
            return {"parts": [{"text": clean_msg, "type": part_type}], "interests": []}

    # Check for simple compound questions ("and", "?")
    system_instruction = render_prompt("router")
    user_prompt = f"Chat history:\n{conversation_context}\n\nStudent message: {clean_msg}"
    
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_prompt},
    ]

    for attempt in range(2):
        try:
            raw_response = await llm.generate(
                messages=messages,
                temperature=0.0,
                max_tokens=300,
            )
            json_text = _clean_json_output(raw_response)
            data = json.loads(json_text)
            
            if isinstance(data, dict) and "parts" in data and isinstance(data["parts"], list) and len(data["parts"]) > 0:
                validated_parts = []
                for p in data["parts"]:
                    if isinstance(p, dict) and "text" in p and "type" in p:
                        ptype = str(p["type"]).lower().strip()
                        if ptype not in VALID_TYPES:
                            ptype = "factual"
                        validated_parts.append({
                            "text": str(p["text"]).strip(),
                            "type": ptype,
                        })
                if validated_parts:
                    interests = data.get("interests", [])
                    if not isinstance(interests, list):
                        interests = []
                    return {
                        "parts": validated_parts,
                        "interests": [str(i).strip() for i in interests if str(i).strip()],
                    }
        except Exception as e:
            logger.warning("Router attempt %d failed: %s. Retrying...", attempt + 1, e)

    # Safe fallback if JSON parsing fails after retry
    fallback_type = "sensitive" if is_crisis_or_distress(clean_msg) else "factual"
    logger.info("Router falling back to single %s part for: %s", fallback_type, clean_msg[:60])
    return {
        "parts": [{"text": clean_msg, "type": fallback_type}],
        "interests": [],
    }
