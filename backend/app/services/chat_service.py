"""Chat service — orchestrator for intent routing, query reformulation, RAG, and streaming."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
import json
import logging
import random
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.providers.base import LLMProvider
from app.schemas.chat import ChatRequest, ChatResponse, SourceReference
from app.services import conversation_service, prompt_service
from app.services.cache_service import get_cached_part, set_cached_part
from app.services.card_service import generate_cards
from app.services.flow_service import (
    detect_flow_trigger,
    execute_wizard_step,
    get_wizard_step_from_history,
)
from app.services.guardrail_service import (
    sanitize_hallucinated_urls,
    verify_numeric_faithfulness,
    verify_url_faithfulness,
)
from app.services.intent_service import classify_intent
from app.services.profile_service import build_counsellor_guidance, extract_student_profile
from app.services.prompt_service import render_prompt
from app.services.rag_service import RAGService
from app.services.reformulation_service import needs_reformulation, reformulate_query
from app.services.router_service import route_and_decompose_message
from app.services.structured_facts_service import get_structured_facts_text
from app.services.suggestion_service import generate_suggestions
from app.services.validator_service import (
    FALLBACK_LOW_CONFIDENCE,
    FALLBACK_VALIDATOR_BLOCK,
    validate_response_grounding,
)
from app.services.video_service import (
    check_video_affirmative_or_negative,
    create_video_card,
    format_video_offer_prompt,
    get_post_video_suggestions,
    get_relevant_videos,
    get_semantic_videos,
    is_explicit_video_query,
    sanitize_answer_video_prompts,
)

logger = logging.getLogger(__name__)

# Indian Standard Time (SR University is located in Warangal, Telangana, India)
IST = timezone(timedelta(hours=5, minutes=30))

STUDENT_AUTH_MESSAGE = (
    "I do not have access to individual student records (such as your personal "
    "attendance percentage, course grades, CGPA, or specific fee payment status). "
    "For access to your individual academic records, please reach out to your "
    "department coordinator, faculty mentor, or the university academic section."
)

OUT_OF_SCOPE_MESSAGE = (
    "I'm SRU Buddy, the dedicated AI assistant for SR University. "
    "I can only help with university-related topics such as admissions, eligibility, "
    "course curriculum, fees, scholarships, hostel accommodation, and placements. "
    "Please ask me anything about SR University!"
)


def get_time_aware_greeting() -> str:
    """Return an IST time-appropriate greeting salutation (SR University is located in Telangana, India)."""
    hour = datetime.now(IST).hour
    if 5 <= hour < 12:
        return "Good morning! ☀️"
    elif 12 <= hour < 17:
        return "Good afternoon! 🌤️"
    elif 17 <= hour < 22:
        return "Good evening! 🌙"
    return "Hello! ✨"


def should_offer_video_tour(message: str) -> bool:
    """Return True only if the user query naturally welcomes a visual or campus tour."""
    msg = message.lower()
    tour_keywords = (
        "campus tour", "hostel tour", "see the campus", "see the hostel",
        "how does it look", "how does the campus look", "look like", "drone",
        "walkthrough", "virtual tour", "campus video", "hostel video", "watch video",
        "video tour", "show video"
    )
    if any(k in msg for k in tour_keywords):
        return True

    # If the user is asking about admissions, fees, ranks, marks, scholarships, or general evaluation, do NOT offer video
    disallowed_keywords = (
        "fee", "fees", "cost", "scholarship", "cutoff", "percentage", "marks", "rank",
        "eligibility", "eligible", "syllabus", "curriculum", "apply", "good",
        "why", "ad", "instagram", "rule", "regulations", "attendance", "mistake", "wrong"
    )
    if any(k in msg for k in disallowed_keywords):
        return False

    facility_keywords = ("campus life", "hostel rooms", "srix", "incubator", "sports facilities")
    return any(k in msg for k in facility_keywords)


def sanitize_staff_contact_numbers(text: str) -> str:
    """Scrub personal mobile phone numbers of internal staff members from student-facing output.
    Keeps official university helpline numbers and national crisis support helplines.
    """
    if not text:
        return text

    # Never sanitize crisis helplines or mental health support responses
    crisis_keywords = ["tele-manas", "aasra", "vandrevala", "kiran", "14416", "9820466726", "1800-599-0019", "helpline", "counselor", "self-harm", "mental health", "distress"]
    if any(k in text.lower() for k in crisis_keywords):
        return text

    # 1. Staff names followed by mobile numbers:
    cleaned = re.sub(
        r"(?:Mr\.|Ms\.|Dr\.)\s+[A-Za-z\.\s]+\s*(?:at|on|:|-)?\s*(?:\+91[\s-]?)?[6-9]\d{9}\b",
        "the IT & Campus Helpdesk (helpdesk@sru.edu.in / 0870-2818333)",
        text,
        flags=re.IGNORECASE,
    )
    # 2. Known individual staff mobiles if mentioned standalone:
    known_staff_mobiles = ["8886522500", "8008917297"]
    for num in known_staff_mobiles:
        cleaned = cleaned.replace(num, "0870-2818333 (Ext. Helpdesk)")
    return cleaned


def strip_source_citations(text: str) -> str:
    """Scrub inline or trailing source citations and references from response text."""
    if not text:
        return text
    # Remove bracketed/parenthesized source mentions like (Source: ...), [Source: ...]
    cleaned = re.sub(
        r"\s*[\(\[](?:sources?|reference|references|doc|document)\s*:[^\]\)]*[\)\]]",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Remove trailing source lines like "Sources cited: ..." or "Source: ..."
    cleaned = re.sub(
        r"(?im)^\s*(?:sources?|references?|sources cited)\s*:.*$",
        "",
        cleaned,
    )
    return cleaned.strip()


GREETING_RESPONSES_INITIAL: list[str] = [
    "{time_salutation} I'm SRU Buddy, your university companion! Feel free to ask about admissions, programs, hostels, or campus life.",
    "{time_salutation} SRU Buddy here! What can I help you explore at SR University today?",
    "{time_salutation} Welcome to SR University! I'm SRU Buddy — ask me anything about admissions, courses, placements, or facilities.",
    "{time_salutation} Looking for information on SR University admissions, courses, or placements? SRU Buddy is here to help!",
]

GREETING_RESPONSES_FOLLOWUP: list[str] = [
    "Hey again! SRU Buddy here — what else can I help you with?",
    "Hi! Still here to help — what would you like to check next?",
    "Hello again! How can I assist you further?",
    "Hi there! Feel free to ask your next question about SR University.",
    "Hey! What's next on your mind regarding SR University?",
    "Hello! Ready for your next question.",
]

ACKNOWLEDGMENT_RESPONSES: list[str] = [
    "Glad to help! Let me know if you have any other questions about SR University.",
    "Got it! Feel free to ask if you need anything else.",
    "Sounds good! I'm here whenever you need more details.",
    "Awesome! Let me know if there's anything else you'd like to explore.",
    "Great! Just let me know if you have any more questions.",
]

THANKS_RESPONSES: list[str] = [
    "You're very welcome! If there's anything else you'd like to know about SR University, feel free to ask.",
    "Happy to help! Let me know if more questions come up.",
    "Anytime! Best of luck, and don't hesitate to reach out if you need more info.",
    "My pleasure! Have a wonderful day, and let me know if you need further assistance.",
]

GOODBYE_RESPONSES: list[str] = [
    "Goodbye! Best of luck with your academic journey at SR University. Have a wonderful day!",
    "Take care! Feel free to come back anytime you have more questions about SR University.",
    "See you! Wishing you all the best with everything at SR University.",
]

HOW_ARE_YOU_RESPONSES: list[str] = [
    "I'm doing great and pumped to help! How can I assist you with SR University today?",
    "Doing well, thank you! I'm ready to answer any questions about SR University.",
    "All good here! What would you like to explore regarding admissions, courses, or campus life?",
]

HELP_RESPONSE: str = (
    "I'm SRU Buddy, here to assist you with everything at SR University! You can ask me about:\n\n"
    "• **Admissions & Eligibility**: Application process, requirements, and deadlines\n"
    "• **Academics & Labs**: Programs, departments, curriculum, and modern lab facilities\n"
    "• **Campus & Hostels**: Accommodation details, mess, transport, and campus amenities\n"
    "• **Placements & Innovation**: Career opportunities, campus placements, and SRiX incubator\n\n"
    "What would you like to explore?"
)

FAST_CONVERSATIONAL_RESPONSES: dict[str, list[str]] = {
    "GREETING": GREETING_RESPONSES_INITIAL,
    "ACKNOWLEDGMENT": ACKNOWLEDGMENT_RESPONSES,
    "THANKS": THANKS_RESPONSES,
    "GOODBYE": GOODBYE_RESPONSES,
    "HOW_ARE_YOU": HOW_ARE_YOU_RESPONSES,
    "HELP": [HELP_RESPONSE],
}


def get_conversational_response(intent: str, has_context: bool = False) -> str:
    """Return a varied, natural conversational response based on intent and context."""
    time_salutation = get_time_aware_greeting()
    if intent == "GREETING":
        if has_context:
            return random.choice(GREETING_RESPONSES_FOLLOWUP)
        template = random.choice(GREETING_RESPONSES_INITIAL)
        return template.format(time_salutation=time_salutation)

    options = FAST_CONVERSATIONAL_RESPONSES.get(intent)
    if options:
        return random.choice(options)

    return f"{time_salutation} I'm SRU Buddy. How can I help you today?"


async def execute_prompt_pack_pipeline(
    message: str,
    conversation_context: str,
    profile: dict,
    llm: LLMProvider,
    rag_service: RAGService | None,
    redis_client: object | None = None,
) -> tuple[str, list[dict]]:
    """Execute Prompt Pack Router -> Parallel Handlers -> Validator -> Merge."""
    routed = await route_and_decompose_message(llm, message, conversation_context)
    parts = routed.get("parts", [{"text": message, "type": "factual"}])
    new_interests = routed.get("interests", [])

    if new_interests:
        profile_interests = profile.get("interests", [])
        for i in new_interests:
            if i not in profile_interests:
                profile_interests.append(i)
        profile["interests"] = profile_interests

    profile_parts = []
    if profile.get("degree"):
        profile_parts.append(f"Degree: {profile['degree']}")
    if profile.get("branch"):
        profile_parts.append(f"Branch: {profile['branch']}")
    if profile.get("score"):
        profile_parts.append(f"Score: {profile['score']}")
    if profile.get("interests"):
        profile_parts.append(f"Interests: {', '.join(profile['interests'])}")
    profile_text = ", ".join(profile_parts) if profile_parts else "Prospective applicant"

    all_sources: list[dict] = []

    async def handle_sub_part(part: dict) -> str:
        ptype = part.get("type", "factual")
        ptext = part.get("text", message)

        if ptype == "chitchat":
            prompt = render_prompt("chitchat", student_profile=profile_text, part_text=ptext)
            ans = await llm.generate([{"role": "user", "content": prompt}], temperature=0.6, max_tokens=250)
            return ans.strip()

        elif ptype == "sensitive":
            prompt = render_prompt("sensitive", part_text=ptext)
            ans = await llm.generate([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=250)
            return ans.strip()

        elif ptype == "out_of_scope":
            prompt = render_prompt("out_of_scope", part_text=ptext)
            ans = await llm.generate([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=200)
            return ans.strip()

        elif ptype == "persuasive":
            highlights_text = ""
            if rag_service:
                chunks, _ = await rag_service.retrieve_with_embedding(ptext, top_k=4)
                highlights_text = "\n\n".join(c["content"] for c in chunks)
                for c in chunks:
                    meta = c.get("metadata", {})
                    if meta.get("document_id") and meta not in all_sources:
                        all_sources.append(meta)
            if not highlights_text:
                highlights_text = get_structured_facts_text(ptext, profile.get("branch"))

            prompt = render_prompt("persuasive", retrieved_highlights=highlights_text, student_profile=profile_text, part_text=ptext)
            ans = await llm.generate([{"role": "user", "content": prompt}], temperature=0.3, max_tokens=300)
            return ans.strip()

        else:  # factual
            # Check response cache if single factual part
            if len(parts) == 1 and redis_client:
                cached = await get_cached_part(
                    redis_client=redis_client,
                    mode="factual",
                    resolved_question=ptext,
                    profile=profile,
                )
                if cached:
                    cached_ans, cached_src = cached
                    for s in cached_src:
                        if s not in all_sources:
                            all_sources.append(s)
                    return cached_ans

            struct_text = get_structured_facts_text(ptext, profile.get("branch"))
            chunks_text = ""
            if rag_service:
                chunks, _ = await rag_service.retrieve_with_embedding(ptext, top_k=5)
                chunks_text = "\n\n".join(f"[{c.get('metadata', {}).get('title', 'Document')}]\n{c['content']}" for c in chunks)
                for c in chunks:
                    meta = c.get("metadata", {})
                    if meta.get("document_id") and meta not in all_sources:
                        all_sources.append(meta)

            prompt = render_prompt(
                "factual",
                structured_facts=struct_text,
                retrieved_chunks=chunks_text,
                student_profile=profile_text,
                part_text=ptext,
            )
            raw_ans = await llm.generate([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=350)

            # Pure code deterministic numeric/date validator
            is_valid, ungrounded = validate_response_grounding(
                raw_ans,
                evidence_text=chunks_text,
                structured_data_text=struct_text,
                user_message=ptext,
                student_profile_text=profile_text,
            )
            if not is_valid:
                logger.warning("Validator detected ungrounded claims: %s. Retrying with strict instruction.", ungrounded)
                retry_prompt = prompt + f"\n\nCRITICAL: Your previous response contained unverified claims {ungrounded}. Use ONLY figures stated in Structured data or Context. Never round or infer numbers."
                retry_ans = await llm.generate([{"role": "user", "content": retry_prompt}], temperature=0.0, max_tokens=350)
                is_retry_valid, retry_ungrounded = validate_response_grounding(
                    retry_ans,
                    evidence_text=chunks_text,
                    structured_data_text=struct_text,
                    user_message=ptext,
                    student_profile_text=profile_text,
                )
                if is_retry_valid:
                    final_ans = retry_ans.strip()
                    if len(parts) == 1 and redis_client:
                        await set_cached_part(
                            redis_client=redis_client,
                            mode="factual",
                            resolved_question=ptext,
                            answer=final_ans,
                            sources=all_sources,
                            profile=profile,
                            part_count=len(parts),
                        )
                    return final_ans
                logger.error("Validator permanently blocked ungrounded numbers: %s. Returning fallback block.", retry_ungrounded)
                return FALLBACK_VALIDATOR_BLOCK

            final_ans = raw_ans.strip()
            if len(parts) == 1 and redis_client:
                await set_cached_part(
                    redis_client=redis_client,
                    mode="factual",
                    resolved_question=ptext,
                    answer=final_ans,
                    sources=all_sources,
                    profile=profile,
                    part_count=len(parts),
                )
            return final_ans

    part_tasks = [handle_sub_part(p) for p in parts]
    part_results = await asyncio.gather(*part_tasks)

    if len(part_results) == 1:
        return part_results[0], all_sources

    formatted_parts = "\n\n".join(f"Part {idx+1} ({parts[idx]['type']}): {res}" for idx, res in enumerate(part_results))
    merge_prompt = render_prompt("merge", part_answers=formatted_parts)
    merged = await llm.generate([{"role": "user", "content": merge_prompt}], temperature=0.0, max_tokens=400)
    return merged.strip(), all_sources


async def handle_chat(
    db: AsyncSession,
    request: ChatRequest,
    llm_provider: LLMProvider,
    rag_service: RAGService | None = None,
    redis_client: object | None = None,
) -> ChatResponse:
    """Process a chat message and return a rich response with suggestions and cards."""
    # 1. Get or create conversation
    conversation = await conversation_service.get_or_create_conversation(
        db, request.session_id, request.conversation_id
    )

    # 2. Save user message
    await conversation_service.add_message(
        db, conversation.id, role="user", content=request.message
    )

    # 3. Build context from recent messages
    recent = await conversation_service.get_recent_messages(db, conversation.id)
    conversation_context = "\n".join(
        f"{m['role']}: {m['content']}" for m in recent[:-1]
    )

    sources: list[dict] = []
    flow_info: dict | None = None
    is_video_yes = False
    is_video_no = False
    semantic_videos: list[dict] = []

    # Check if user is confirming or declining a prior video tour offer
    is_video_yes, is_video_no = check_video_affirmative_or_negative(
        request.message, recent
    )

    if is_video_yes:
        last_asst_msg = next((m for m in reversed(recent[:-1]) if m.get("role") == "assistant"), None)
        asst_meta = last_asst_msg.get("metadata") if isinstance(last_asst_msg, dict) else {}
        asst_meta = asst_meta if isinstance(asst_meta, dict) else {}
        matching_videos = asst_meta.get("matched_videos")
        if not matching_videos and rag_service:
            prior_user_msg = next((m for m in reversed(recent[:-1]) if m.get("role") == "user"), None)
            if prior_user_msg:
                try:
                    prior_embs = await rag_service.embeddings.embed([prior_user_msg["content"]])
                    matching_videos = get_semantic_videos(prior_embs[0], limit=2, max_distance=0.30)
                except Exception:
                    matching_videos = None

        cat = matching_videos[0].get("category", "Campus Life") if matching_videos else "Campus Life"
        if matching_videos:
            vid_links = "\n".join(
                f"- 🎥 [{v.get('title', 'Watch Video Tour')}]({v.get('url')})" for v in matching_videos
            )
            answer = f"Here is the official video tour of {cat}:\n\n{vid_links}"
        else:
            answer = (
                f"Here is the official SR University YouTube channel to explore {cat} tours: "
                f"[SR University Official Channel](https://www.youtube.com/@SRUniversity/videos)"
            )
        cards = [create_video_card(matching_videos, is_explicit=True)] if matching_videos else []
        suggestions = get_post_video_suggestions(cat)
        intent = "UNIVERSITY"
        profile = extract_student_profile(recent)

    elif is_video_no:
        answer = "No problem at all! Feel free to ask anything else about SR University."
        cards = []
        suggestions = [
            "🎯 B.Tech Admissions",
            "💰 Fee Structure",
            "📊 Placement Records",
            "🔬 Lab Facilities",
        ]
        intent = "ACKNOWLEDGMENT"
        profile = extract_student_profile(recent)

    # Check for guided conversation flow (Admission Wizard)
    elif detect_flow_trigger(request.message) is not None or get_wizard_step_from_history(recent[:-1], request.message):
        wizard_step = get_wizard_step_from_history(recent[:-1], request.message)
        if not wizard_step:
            wizard_step = {
                "flow_name": "admission_wizard",
                "step": 1,
                "total_steps": 4,
                "step_title": "Choose Degree Program",
                "completed": False,
                "options": ["🎓 B.Tech", "📘 M.Tech", "💼 MBA", "🔬 Ph.D."],
            }
        answer, flow_info = execute_wizard_step(wizard_step)
        intent = "ADMISSION_FLOW"
        profile = extract_student_profile(recent)
    else:
        # 4. Classify intent on the RAW message
        intent, confidence = await classify_intent(
            request.message,
            conversation_context=conversation_context,
            llm_provider=llm_provider,
        )
        logger.info(
            "Message '%s...' classified as %s (confidence=%.2f)",
            request.message[:30], intent, confidence,
        )

        profile = extract_student_profile(recent)

        # 5. Route and generate response
        if intent == "STUDENT_SPECIFIC":
            answer = STUDENT_AUTH_MESSAGE
            logger.info("Handled via STUDENT_SPECIFIC auth guardrail")

        elif intent == "OUT_OF_SCOPE":
            answer = OUT_OF_SCOPE_MESSAGE
            logger.info("Handled via OUT_OF_SCOPE guardrail")

        elif intent in FAST_CONVERSATIONAL_RESPONSES:
            has_context = bool(conversation_context.strip())
            answer = get_conversational_response(intent, has_context=has_context)
            logger.info("Handled via fast conversational response (%s)", intent)

        elif intent in ("UNIVERSITY", "GENERAL_CONVERSATION", "UNKNOWN"):
            answer, sources = await execute_prompt_pack_pipeline(
                message=request.message,
                conversation_context=conversation_context,
                profile=profile,
                llm=llm_provider,
                rag_service=rag_service,
                redis_client=redis_client,
            )
            logger.info("Handled via Prompt Pack Pipeline (answer length: %d)", len(answer))

        else:
            system_prompt = prompt_service.load_prompt("system")
            messages = [{"role": "system", "content": system_prompt}] + recent
            answer = await llm_provider.generate(messages)
            logger.info("Handled via conversational LLM (%s)", intent)

    # Pure Semantic Vector Search for Video Recommendations (Zero Keywords)
    explicit_video = is_explicit_video_query(request.message)
    query_embedding = getattr(rag_service, "last_query_embedding", None)

    if not is_video_yes and not is_video_no:
        if query_embedding:
            semantic_videos = get_semantic_videos(query_embedding, limit=2, max_distance=0.25)
            if semantic_videos and not explicit_video and intent == "UNIVERSITY" and should_offer_video_tour(request.message):
                cat = semantic_videos[0].get("category", "our campus")
                answer = format_video_offer_prompt(answer, cat)
            else:
                answer = sanitize_answer_video_prompts(answer)
        else:
            answer = sanitize_answer_video_prompts(answer)

        # 6. Generate smart suggestion chips and rich cards
        suggestions = generate_suggestions(
            intent=intent,
            user_message=request.message,
            answer=answer,
            sources=sources,
            profile=profile,
            flow_state=flow_info,
        )
        if semantic_videos and not explicit_video and intent == "UNIVERSITY" and should_offer_video_tour(request.message):
            suggestions = ["🎥 Yes, watch video", "❌ No, thanks"] + [s for s in suggestions if "video" not in s.lower()][:2]

        cards = generate_cards(
            user_message=request.message,
            answer=answer,
            profile=profile,
            sources=sources,
            query_embedding=query_embedding,
            is_video_confirmed=is_video_yes,
        )

    # Sanitize any personal staff mobile numbers and strip citations from output
    answer = sanitize_staff_contact_numbers(answer)
    answer = strip_source_citations(answer)

    # 7. Save assistant message with metadata
    assistant_msg = await conversation_service.add_message(
        db,
        conversation.id,
        role="assistant",
        content=answer,
        model=settings.LLM_MODEL,
        sources=sources if sources else None,
        metadata={
            "suggestions": suggestions,
            "cards": cards,
            "flow": flow_info,
            "matched_videos": semantic_videos if semantic_videos else None,
            "video_offer": bool(semantic_videos and not explicit_video and intent == "UNIVERSITY"),
        },
    )

    # 8. Auto-title on first exchange
    if conversation.title == "New conversation":
        title = request.message[:50].strip()
        if len(request.message) > 50:
            title += "..."
        await conversation_service.update_conversation_title(
            db, conversation.id, title
        )

    # 9. Return response
    return ChatResponse(
        conversation_id=conversation.id,
        message_id=assistant_msg.id,
        answer=answer,
        sources=[SourceReference(**s) for s in sources] if (getattr(settings, "SHOW_SOURCES", False) and sources) else [],
        suggestions=suggestions,
        cards=cards,
        flow=flow_info,
        model=settings.LLM_MODEL,
    )


def chunk_text_stream(text: str) -> list[str]:
    """Split text into streamable token chunks while preserving all whitespace and newlines."""
    chunks = re.findall(r"\S+\s*|\s+", text)
    return chunks if chunks else [text]


async def handle_chat_stream(
    db: AsyncSession,
    request: ChatRequest,
    llm_provider: LLMProvider,
    rag_service: RAGService | None = None,
    redis_client: object | None = None,
) -> AsyncIterator[str]:
    """Process a chat message and stream tokens via Server-Sent Events (SSE)."""
    try:
        # 1. Get or create conversation
        conversation = await conversation_service.get_or_create_conversation(
            db, request.session_id, request.conversation_id
        )

        # 2. Save user message
        await conversation_service.add_message(
            db, conversation.id, role="user", content=request.message
        )

        # Send initial event
        yield f"data: {json.dumps({'type': 'start', 'conversation_id': str(conversation.id)})}\n\n"

        # 3. Build context
        recent = await conversation_service.get_recent_messages(db, conversation.id)
        conversation_context = "\n".join(
            f"{m['role']}: {m['content']}" for m in recent[:-1]
        )

        sources: list[dict] = []
        flow_info: dict | None = None
        answer = ""
        query_embedding: list[float] | None = None
        profile: dict = {}

        # Check for guided flow or video confirmation/decline
        is_video_yes, is_video_no = check_video_affirmative_or_negative(
            request.message, recent
        )

        if is_video_yes:
            last_asst_msg = next((m for m in reversed(recent[:-1]) if m.get("role") == "assistant"), None)
            asst_meta = last_asst_msg.get("metadata") if isinstance(last_asst_msg, dict) else {}
            asst_meta = asst_meta if isinstance(asst_meta, dict) else {}
            matching_videos = asst_meta.get("matched_videos")
            if not matching_videos and rag_service:
                prior_user_msg = next((m for m in reversed(recent[:-1]) if m.get("role") == "user"), None)
                if prior_user_msg:
                    try:
                        prior_embs = await rag_service.embeddings.embed([prior_user_msg["content"]])
                        matching_videos = get_semantic_videos(prior_embs[0], limit=2, max_distance=0.30)
                    except Exception:
                        matching_videos = None

            cat = matching_videos[0].get("category", "Campus Life") if matching_videos else "Campus Life"
            if matching_videos:
                vid_links = "\n".join(
                    f"- 🎥 [{v.get('title', 'Watch Video Tour')}]({v.get('url')})" for v in matching_videos
                )
                answer = f"Here is the official video tour of {cat}:\n\n{vid_links}"
            else:
                answer = (
                    f"Here is the official SR University YouTube channel to explore {cat} tours: "
                    f"[SR University Official Channel](https://www.youtube.com/@SRUniversity/videos)"
                )
            cards = [create_video_card(matching_videos, is_explicit=True)] if matching_videos else []
            suggestions = get_post_video_suggestions(cat)
            intent = "UNIVERSITY"
            profile = {}

            for chunk in chunk_text_stream(answer):
                yield f"data: {json.dumps({'type': 'token', 'delta': chunk})}\n\n"
                await asyncio.sleep(0.01)

        elif is_video_no:
            answer = "No problem at all! Feel free to ask anything else about SR University."
            cards = []
            suggestions = [
                "🎯 B.Tech Admissions",
                "💰 Fee Structure",
                "📊 Placement Records",
                "🔬 Lab Facilities",
            ]
            intent = "ACKNOWLEDGMENT"
            profile = {}

            for chunk in chunk_text_stream(answer):
                yield f"data: {json.dumps({'type': 'token', 'delta': chunk})}\n\n"
                await asyncio.sleep(0.01)

        elif detect_flow_trigger(request.message) is not None or get_wizard_step_from_history(recent[:-1], request.message):
            wizard_step = get_wizard_step_from_history(recent[:-1], request.message)
            if not wizard_step:
                wizard_step = {
                    "flow_name": "admission_wizard",
                    "step": 1,
                    "total_steps": 4,
                    "step_title": "Choose Degree Program",
                    "completed": False,
                    "options": ["🎓 B.Tech", "📘 M.Tech", "💼 MBA", "🔬 Ph.D."],
                }
            answer, flow_info = execute_wizard_step(wizard_step)
            intent = "ADMISSION_FLOW"
            # Lazy-fetch all_user_messages for non-UNIVERSITY paths
            all_user_messages = await conversation_service.get_all_user_messages(db, conversation.id)
            profile = extract_student_profile(all_user_messages)

            # Stream words smoothly preserving all formatting
            for chunk in chunk_text_stream(answer):
                yield f"data: {json.dumps({'type': 'token', 'delta': chunk})}\n\n"
                await asyncio.sleep(0.012)

        else:
            # Classify intent
            intent, confidence = await classify_intent(
                request.message,
                conversation_context=conversation_context,
                llm_provider=llm_provider,
            )

            if intent == "STUDENT_SPECIFIC":
                # Lazy-fetch for non-UNIVERSITY path
                all_user_messages = await conversation_service.get_all_user_messages(db, conversation.id)
                profile = extract_student_profile(all_user_messages)
                answer = STUDENT_AUTH_MESSAGE
                for chunk in chunk_text_stream(answer):
                    yield f"data: {json.dumps({'type': 'token', 'delta': chunk})}\n\n"
                    await asyncio.sleep(0.012)

            elif intent == "OUT_OF_SCOPE":
                # Lazy-fetch for non-UNIVERSITY path
                all_user_messages = await conversation_service.get_all_user_messages(db, conversation.id)
                profile = extract_student_profile(all_user_messages)
                answer = OUT_OF_SCOPE_MESSAGE
                for chunk in chunk_text_stream(answer):
                    yield f"data: {json.dumps({'type': 'token', 'delta': chunk})}\n\n"
                    await asyncio.sleep(0.012)

            elif intent in FAST_CONVERSATIONAL_RESPONSES:
                # Lazy-fetch for non-UNIVERSITY path
                all_user_messages = await conversation_service.get_all_user_messages(db, conversation.id)
                profile = extract_student_profile(all_user_messages)
                has_context = bool(conversation_context.strip())
                answer = get_conversational_response(intent, has_context=has_context)
                for chunk in chunk_text_stream(answer):
                    yield f"data: {json.dumps({'type': 'token', 'delta': chunk})}\n\n"
                    await asyncio.sleep(0.012)

            elif intent in ("UNIVERSITY", "GENERAL_CONVERSATION", "UNKNOWN"):
                all_user_messages = await conversation_service.get_all_user_messages(db, conversation.id)
                profile = extract_student_profile(all_user_messages)
                answer, sources = await execute_prompt_pack_pipeline(
                    message=request.message,
                    conversation_context=conversation_context,
                    profile=profile,
                    llm=llm_provider,
                    rag_service=rag_service,
                    redis_client=redis_client,
                )
                for chunk in chunk_text_stream(answer):
                    yield f"data: {json.dumps({'type': 'token', 'delta': chunk})}\n\n"
                    await asyncio.sleep(0.012)

            else:
                system_prompt = prompt_service.load_prompt("system")
                guidance = build_counsellor_guidance(profile, current_query=request.message)
                if guidance:
                    system_prompt = f"{system_prompt}\n\n{guidance}".strip()
                messages = [{"role": "system", "content": system_prompt}] + recent
                streamed_tokens = []
                async for token in llm_provider.stream(messages):
                    streamed_tokens.append(token)
                    yield f"data: {json.dumps({'type': 'token', 'delta': token})}\n\n"
                answer = "".join(streamed_tokens)

        semantic_videos = []
        explicit_video = is_explicit_video_query(request.message)

        if not is_video_yes and not is_video_no:
            if not query_embedding and rag_service:
                try:
                    query_embedding = await rag_service.embeddings.embed_single(request.message)
                except Exception:
                    query_embedding = None

            if query_embedding:
                semantic_videos = get_semantic_videos(query_embedding, limit=2, max_distance=0.25)
                if semantic_videos and not explicit_video and intent == "UNIVERSITY" and should_offer_video_tour(request.message):
                    cat = semantic_videos[0].get("category", "our campus")
                    new_answer = format_video_offer_prompt(answer, cat)
                    if new_answer != answer:
                        delta_prompt = new_answer[len(answer):]
                        if delta_prompt:
                            for chunk in chunk_text_stream(delta_prompt):
                                yield f"data: {json.dumps({'type': 'token', 'delta': chunk})}\n\n"
                        answer = new_answer
                else:
                    answer = sanitize_answer_video_prompts(answer)
            else:
                answer = sanitize_answer_video_prompts(answer)

            # Suggestions and rich cards
            suggestions = generate_suggestions(
                intent=intent,
                user_message=request.message,
                answer=answer,
                sources=sources,
                profile=profile,
                flow_state=flow_info,
            )
            if semantic_videos and not explicit_video and intent == "UNIVERSITY" and should_offer_video_tour(request.message):
                suggestions = ["🎥 Yes, watch video", "❌ No, thanks"] + [s for s in suggestions if "video" not in s.lower()][:2]

            cards = generate_cards(
                user_message=request.message,
                answer=answer,
                profile=profile,
                sources=sources,
                query_embedding=query_embedding,
                is_video_confirmed=is_video_yes,
            )

        # Sanitize any personal staff mobile numbers and strip citations from output
        answer = sanitize_staff_contact_numbers(answer)
        answer = strip_source_citations(answer)

        # Save to database
        assistant_msg = await conversation_service.add_message(
            db,
            conversation.id,
            role="assistant",
            content=answer,
            model=settings.LLM_MODEL,
            sources=sources if sources else None,
            metadata={
                "suggestions": suggestions,
                "cards": cards,
                "flow": flow_info,
                "matched_videos": semantic_videos if semantic_videos else None,
                "video_offer": bool(semantic_videos and not explicit_video and intent == "UNIVERSITY"),
            },
        )

        if conversation.title == "New conversation":
            title = request.message[:50].strip()
            if len(request.message) > 50:
                title += "..."
            await conversation_service.update_conversation_title(
                db, conversation.id, title
            )

        # Final completion event (sources gated by SHOW_SOURCES setting)
        client_sources = sources if getattr(settings, "SHOW_SOURCES", False) else []
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': str(conversation.id), 'message_id': str(assistant_msg.id), 'answer': answer, 'sources': client_sources, 'suggestions': suggestions, 'cards': cards, 'flow': flow_info, 'model': settings.LLM_MODEL})}\n\n"

    except Exception as e:
        logger.error("Chat stream error: %s", e, exc_info=True)
        user_message = "Something went wrong while connecting to the university server. Please try again in a moment."
        yield f"data: {json.dumps({'type': 'error', 'detail': user_message})}\n\n"
