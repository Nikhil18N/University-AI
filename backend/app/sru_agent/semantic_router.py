"""Semantic Response Router: Context-aware, confidence-based intent and policy routing."""

from __future__ import annotations
import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from app.sru_agent.policy_models import ApprovalStatus, ResponseMode, RoutingDecision
from app.sru_agent import policy_service

# Threshold above which a query is routed to an approved policy; below this, it falls back to RAG.
DEFAULT_CONFIDENCE_THRESHOLD = 0.52

# Regional / colloquial translations for multilingual semantic matching
_COLLOQUIAL_TRANSLATIONS = [
    (r"\b(?:sru\s+lo\s+join\s+avvadam\s+worth\s+ah\s+kaada|join\s+avvadam\s+worth\s+ah)\b", "why should i choose sru is sru actually worth joining"),
    (r"\b(?:placements\s+baguntaya|placements\s+ela\s+untayi)\b", "how are the placements at sru"),
    (r"\b(?:avg\s+package\s+entha)\b", "what is the average placement package"),
    (r"\b(?:hostel\s+food\s+ela\s+untadi|mess\s+food\s+ela\s+untadi)\b", "how is the hostel mess food"),
    (r"\b(?:seat\s+confirm\s+ga\s+vastunda|seat\s+confirm\s+avtunda)\b", "is seat admission guaranteed"),
    (r"\b(?:job\s+guarantee\s+unda)\b", "is there a job placement guarantee"),
    (r"\bsr\s*university\b", "sru"),
    (r"\bpick\b", "choose"),
    (r"\bselect\b", "choose"),
    (r"\bopt\b", "choose"),
    (r"\b(?:bro|anna|bhai|yaar|andi|ayya)\b", ""),
]


def _normalize_query(text: str) -> str:
    cleaned = (text or "").lower().strip()
    for pattern, repl in _COLLOQUIAL_TRANSLATIONS:
        cleaned = re.sub(pattern, repl, cleaned)
    # Strip punctuation and multiple spaces
    cleaned = re.sub(r"[^\w\s%]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _tokenize(text: str) -> set[str]:
    # Character 3-grams and words for robust semantic match
    words = [w for w in text.split() if len(w) > 1]
    tokens = set(words)
    # Add bigrams
    for i in range(len(words) - 1):
        tokens.add(f"{words[i]}_{words[i+1]}")
    return tokens


_STOPWORDS = {
    "tell", "me", "about", "the", "a", "an", "is", "are", "of", "to", "for",
    "in", "it", "on", "at", "as", "by", "with", "this", "that", "i", "my",
    "your", "can", "do", "does", "any", "please", "some", "our",
}
_QUESTION_WORDS = {"where", "when", "who", "why", "how", "what", "which"}


def _compute_semantic_similarity(query: str, anchor: str) -> float:
    """Compute semantic match score using content-aware Jaccard and F1 overlap."""
    q_norm = _normalize_query(query)
    a_norm = _normalize_query(anchor)

    if q_norm == a_norm:
        return 1.0

    q_words = set(q_norm.split())
    a_words = set(a_norm.split())

    extra_words = (q_words ^ a_words) - _STOPWORDS
    if not extra_words:
        return 0.96

    if len(q_norm.split()) >= 3 and (q_norm in a_norm or a_norm in q_norm):
        if not ((q_words - a_words) - _STOPWORDS - {"other", "colleges", "college", "destination", "engineering"}):
            return 0.88

    q_qwords = q_words.intersection(_QUESTION_WORDS)
    a_qwords = a_words.intersection(_QUESTION_WORDS)
    if q_qwords and a_qwords and not q_qwords.intersection(a_qwords):
        if "where" in q_qwords or "when" in q_qwords or "who" in q_qwords:
            return 0.0

    q_content = q_words - _STOPWORDS
    a_content = a_words - _STOPWORDS
    if a_content and not q_content.intersection(a_content):
        return 0.0

    c_inter = len(q_content.intersection(a_content))
    c_union = len(q_content.union(a_content))
    c_jaccard = c_inter / c_union if c_union else 0.0

    inter = len(q_words.intersection(a_words))
    union = len(q_words.union(a_words))
    jaccard = inter / union if union else 0.0

    rec = inter / max(len(a_words), 1)
    prec = inter / max(len(q_words), 1)
    f1 = (2 * rec * prec) / (rec + prec) if (rec + prec) else 0.0

    combined = (0.45 * c_jaccard) + (0.35 * f1) + (0.2 * jaccard)
    # Penalize extra unmatched content words in query
    extra_content = q_content - a_content
    if extra_content and len(q_norm.split()) > len(a_norm.split()):
        combined -= (len(extra_content) * 0.18)

    return round(max(min(combined, 1.0), 0.0), 3)


_INQUIRY_INDICATORS = {
    "is", "are", "can", "could", "would", "will", "do", "does", "did",
    "what", "where", "how", "why", "which", "who", "tell", "explain", "describe", "show", "give",
}


def _is_inquiry(chunk: str) -> bool:
    c = chunk.strip().lower()
    if c.endswith("?"):
        return True
    words = set(re.findall(r"\b\w+\b", c))
    return bool(words.intersection(_INQUIRY_INDICATORS))


def decompose_multi_questions(text: str) -> list[str]:
    """Split compound or multi-part student inquiries into individual sub-questions."""
    s = re.sub(r"\?+", " ? <SPLIT> ", text or "")
    s = re.sub(r"(?<!\d)(?:\b\d{1,2}[.)]\s+)", " <SPLIT> ", s)
    s = re.sub(r"(?i)\s+(?:and(?:\s+also)?|also|as\s+well\s+as|plus)\s+(?=(?:is|are|can|do|does|what|where|how|why|which|who|tell|explain|give)\b)", " <SPLIT> ", s)
    s = re.sub(r"(?i),\s*(?=(?:is|are|can|do|does|what|where|how|why|which|who)\b)", " <SPLIT> ", s)
    s = re.sub(r"[;\n]+", " <SPLIT> ", s)
    
    parts = [p.strip() for p in s.split("<SPLIT>") if p.strip() and p.strip() != "?"]
    inquiries = []
    prefix = ""
    for p in parts:
        p_clean = re.sub(r"\s+\?", "?", p).strip()
        p_clean = re.sub(r"[,\s;]+$", "", p_clean).strip()
        if not p_clean:
            continue
        if _is_inquiry(p_clean):
            if prefix:
                inquiries.append(f"{prefix} {p_clean}")
                prefix = ""
            else:
                inquiries.append(p_clean)
        else:
            prefix = p_clean

    return inquiries if inquiries else ([text.strip()] if text and text.strip() else [])


class SemanticRouter:
    """Routes user queries semantically to Approved Answer Policies or RAG fallback."""

    def __init__(self, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD):
        self.threshold = confidence_threshold

    def route(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        conversation_state: Optional[Dict[str, Any]] = None,
    ) -> RoutingDecision:
        history = conversation_history or []
        state = conversation_state or {}

        # 1. Context Awareness: Check if user is in an active admission intake
        intake = state.get("fee_intake") or {}
        admission_stage = state.get("admission_stage")
        norm_msg = _normalize_query(message)

        # Multi-question understanding: Detect compound inquiries containing distinct questions
        sub_questions = decompose_multi_questions(message)
        if len(sub_questions) > 1:
            return RoutingDecision(
                intent_id="MULTI_QUESTION_QUERY",
                policy_id=None,
                response_mode=ResponseMode.RAG,
                confidence=0.92,
                evidence_ids=[],
                is_fallback=True,
                fallback_reason=f"Multi-question inquiry decomposed into {len(sub_questions)} questions: {sub_questions}",
                reasoning=f"Compound question requiring multi-topic retrieval: {sub_questions}",
            )

        # Resume signals: "continue my admission", "continue counselling", "ok continue"
        is_resume_signal = bool(re.search(r"\b(?:continue(?:\s+my)?\s+(?:admission|counselling|intake)|resume(?:\s+my)?\s+admission|go\s+back\s+to\s+admission)\b", norm_msg))
        if is_resume_signal and state.get("paused_intent"):
            paused = state.get("paused_intent")
            return RoutingDecision(
                intent_id=paused,
                policy_id=None,
                response_mode=ResponseMode.GUIDED,
                confidence=0.95,
                reasoning="Resuming previously paused admission workflow",
            )

        # Check for bare marks / rank inputs during admission intake
        is_bare_marks = bool(re.fullmatch(r"(?:i\s+(?:got|scored)\s+)?\d{2,4}(?:\.\d+)?\s*(?:marks?|%|percent)?", norm_msg))
        if is_bare_marks and (intake.get("waiting_for") or admission_stage in ("marks_intake", "program_selection")):
            return RoutingDecision(
                intent_id="ADMISSION_DATA_INPUT",
                policy_id=None,
                response_mode=ResponseMode.FIXED,
                confidence=0.98,
                reasoning="Active admission data intake turn; preserving context",
            )

        # 2. Check semantic similarity across all approved policies
        policies = policy_service.get_all_policies(status=ApprovalStatus.APPROVED)
        best_match = None
        best_score = 0.0
        matched_anchor = None

        for pol in policies:
            if pol.intent_id in ("ABOUT_SRU", "WHY_CHOOSE_SRU"):
                if any(k in norm_msg for k in (
                    "fee", "fees", "cost", "eligibility", "hostel", "placement", "placements",
                    "branch", "branches", "curfew", "scholarship", "cyber", "cybersecurity",
                    "security", "cloud", "data science", "syllabus", "available", "library",
                )):
                    continue
            if pol.intent_id == "FUTURE_YEAR_FEE":
                has_future = bool(re.search(r"\b(?:202[8-9]|203\d|future|upcoming)\b", norm_msg))
                if not has_future:
                    continue
            for anchor in pol.semantic_anchors:
                score = _compute_semantic_similarity(message, anchor)
                if score > best_score:
                    best_score = score
                    best_match = pol
                    matched_anchor = anchor

        # 3. Confidence threshold decision
        if best_match and best_score >= self.threshold:
            # Check if this query is an interruption to an ongoing workflow
            return RoutingDecision(
                intent_id=best_match.intent_id,
                policy_id=best_match.policy_id,
                policy_version=best_match.version,
                response_mode=best_match.response_mode,
                confidence=best_score,
                evidence_ids=best_match.evidence_requirements,
                is_fallback=False,
                matched_anchor=matched_anchor,
                reasoning=f"Matched policy '{best_match.policy_id}' via anchor '{matched_anchor}' with score {best_score}",
            )

        # 4. Fallback to RAG if no approved policy matches reliably
        return RoutingDecision(
            intent_id="GENERAL_RAG_QUERY",
            policy_id=None,
            policy_version=None,
            response_mode=ResponseMode.RAG,
            confidence=best_score,
            is_fallback=True,
            fallback_reason=f"No approved policy met confidence threshold ({best_score} < {self.threshold})",
            reasoning="Falling back to grounded vector RAG generation",
        )


# Singleton router
_default_router = SemanticRouter()


def route_message(
    message: str,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    conversation_state: Optional[Dict[str, Any]] = None,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> RoutingDecision:
    """Helper to route a message using the semantic router."""
    router = _default_router if threshold == DEFAULT_CONFIDENCE_THRESHOLD else SemanticRouter(threshold)
    return router.route(message, conversation_history, conversation_state)
