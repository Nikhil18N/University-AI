"""Chat service — orchestrator for intent routing, query reformulation, RAG, and streaming."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
import json
import logging
import random
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.providers.base import LLMProvider
from app.schemas.chat import ChatRequest, ChatResponse, SourceReference
from app.services import conversation_service, prompt_service
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
from app.services.rag_service import RAGService
from app.services.reformulation_service import needs_reformulation, reformulate_query
from app.services.suggestion_service import generate_suggestions

logger = logging.getLogger(__name__)

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
    """Return a time-appropriate greeting salutation."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Good morning! ☀️"
    elif 12 <= hour < 17:
        return "Good afternoon! 🌤️"
    elif 17 <= hour < 22:
        return "Good evening! 🌙"
    return "Hey night owl! 🦉"


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


async def handle_chat(
    db: AsyncSession,
    request: ChatRequest,
    llm_provider: LLMProvider,
    rag_service: RAGService | None = None,
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

    # Check for guided conversation flow (Admission Wizard)
    is_wizard_trigger = detect_flow_trigger(request.message) is not None
    wizard_step = get_wizard_step_from_history(recent[:-1], request.message)

    if is_wizard_trigger or wizard_step:
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

        elif intent == "UNIVERSITY" and rag_service:
            search_query = request.message
            if needs_reformulation(request.message, conversation_context):
                search_query = await reformulate_query(
                    request.message,
                    conversation_context=conversation_context,
                    llm_provider=llm_provider,
                )

            guidance = build_counsellor_guidance(profile, current_query=request.message)
            rag_context = conversation_context
            if guidance:
                rag_context = f"{rag_context}\n\n{guidance}".strip() if rag_context else guidance

            answer, sources = await rag_service.query(
                question=request.message,
                search_query=search_query,
                conversation_context=rag_context,
            )
            logger.info("Handled via RAG pipeline (search query: '%s')", search_query[:50])

        else:
            system_prompt = prompt_service.load_prompt("system")
            messages = [{"role": "system", "content": system_prompt}] + recent
            answer = await llm_provider.generate(messages)
            logger.info("Handled via conversational LLM (%s)", intent)

    # 6. Generate smart suggestion chips and rich cards
    suggestions = generate_suggestions(
        intent=intent,
        user_message=request.message,
        answer=answer,
        sources=sources,
        profile=profile,
        flow_state=flow_info,
    )
    cards = generate_cards(
        user_message=request.message,
        answer=answer,
        profile=profile,
    )

    # 7. Save assistant message with metadata
    assistant_msg = await conversation_service.add_message(
        db,
        conversation.id,
        role="assistant",
        content=answer,
        model=settings.LLM_MODEL,
        sources=sources if sources else None,
        metadata={"suggestions": suggestions, "cards": cards, "flow": flow_info},
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
        sources=[SourceReference(**s) for s in sources] if sources else [],
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
        all_user_messages = await conversation_service.get_all_user_messages(db, conversation.id)
        conversation_context = "\n".join(
            f"{m['role']}: {m['content']}" for m in recent[:-1]
        )

        sources: list[dict] = []
        flow_info: dict | None = None
        answer = ""

        # Check for guided flow
        is_wizard_trigger = detect_flow_trigger(request.message) is not None
        wizard_step = get_wizard_step_from_history(recent[:-1], request.message)

        if is_wizard_trigger or wizard_step:
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
            profile = extract_student_profile(all_user_messages)

            if intent == "STUDENT_SPECIFIC":
                answer = STUDENT_AUTH_MESSAGE
                for chunk in chunk_text_stream(answer):
                    yield f"data: {json.dumps({'type': 'token', 'delta': chunk})}\n\n"
                    await asyncio.sleep(0.012)

            elif intent == "OUT_OF_SCOPE":
                answer = OUT_OF_SCOPE_MESSAGE
                for chunk in chunk_text_stream(answer):
                    yield f"data: {json.dumps({'type': 'token', 'delta': chunk})}\n\n"
                    await asyncio.sleep(0.012)

            elif intent in FAST_CONVERSATIONAL_RESPONSES:
                has_context = bool(conversation_context.strip())
                answer = get_conversational_response(intent, has_context=has_context)
                for chunk in chunk_text_stream(answer):
                    yield f"data: {json.dumps({'type': 'token', 'delta': chunk})}\n\n"
                    await asyncio.sleep(0.012)

            elif intent == "UNIVERSITY" and rag_service:
                search_query = request.message
                if needs_reformulation(request.message, conversation_context):
                    search_query = await reformulate_query(
                        request.message,
                        conversation_context=conversation_context,
                        llm_provider=llm_provider,
                    )

                chunks = await rag_service.retrieve(search_query)
                clean_q = request.message.lower().strip(" .!?,")
                effective_q = request.message
                if search_query and (
                    clean_q in ("yes", "yeah", "yep", "sure", "ok", "tell me more", "more details", "go ahead", "definitely", "yes please", "why not")
                    or len(clean_q.split()) <= 2
                ):
                    effective_q = f"{request.message} ({search_query})"

                guidance = build_counsellor_guidance(profile, current_query=request.message)
                rag_context = conversation_context
                if guidance:
                    rag_context = f"{rag_context}\n\n{guidance}".strip() if rag_context else guidance

                if not chunks:
                    answer = (
                        "I couldn't find relevant information in the university documents "
                        "to answer that question. You may want to check with the university "
                        "office directly."
                    )
                    for chunk in chunk_text_stream(answer):
                        yield f"data: {json.dumps({'type': 'token', 'delta': chunk})}\n\n"
                        await asyncio.sleep(0.012)
                else:
                    messages, sources, evidence_text = await rag_service.prepare_rag_request(
                        effective_q, rag_context, chunks
                    )
                    streamed_tokens = []
                    async for token in llm_provider.stream(messages, temperature=0.3):
                        streamed_tokens.append(token)
                        yield f"data: {json.dumps({'type': 'token', 'delta': token})}\n\n"

                    answer = "".join(streamed_tokens)

                    # Check runtime hallucination guardrails
                    is_faithful, unsupported = verify_numeric_faithfulness(
                        answer=answer,
                        evidence_text=evidence_text,
                        conversation_context=rag_context,
                        question=effective_q,
                    )
                    if not is_faithful:
                        logger.warning("Stream correction triggered for unsupported numbers %s", unsupported)
                        correction_instruction = (
                            f"CORRECTION: Your previous draft stated number(s) or percentage(s) that are NOT present "
                            f"in the evidence or conversation: {', '.join(unsupported)}. "
                            f"Rewrite your response using strictly verified numbers from the evidence."
                        )
                        correction_messages = messages + [
                            {"role": "assistant", "content": answer},
                            {"role": "user", "content": correction_instruction},
                        ]
                        corrected = await llm_provider.generate(correction_messages, temperature=0.1)
                        second_check, still_unsupported = verify_numeric_faithfulness(
                            corrected, evidence_text, rag_context, effective_q
                        )
                        if second_check or len(still_unsupported) < len(unsupported):
                            answer = corrected

                    is_url_faithful, unverified_urls = verify_url_faithfulness(answer, evidence_text)
                    if not is_url_faithful:
                        answer = sanitize_hallucinated_urls(answer, unverified_urls)

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

        # Suggestions and rich cards
        suggestions = generate_suggestions(
            intent=intent,
            user_message=request.message,
            answer=answer,
            sources=sources,
            profile=profile,
            flow_state=flow_info,
        )
        cards = generate_cards(
            user_message=request.message,
            answer=answer,
            profile=profile,
        )

        # Save to database
        assistant_msg = await conversation_service.add_message(
            db,
            conversation.id,
            role="assistant",
            content=answer,
            model=settings.LLM_MODEL,
            sources=sources if sources else None,
            metadata={"suggestions": suggestions, "cards": cards, "flow": flow_info},
        )

        if conversation.title == "New conversation":
            title = request.message[:50].strip()
            if len(request.message) > 50:
                title += "..."
            await conversation_service.update_conversation_title(
                db, conversation.id, title
            )

        # Final completion event
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': str(conversation.id), 'message_id': str(assistant_msg.id), 'answer': answer, 'sources': sources, 'suggestions': suggestions, 'cards': cards, 'flow': flow_info, 'model': settings.LLM_MODEL})}\n\n"

    except Exception as e:
        logger.error("Chat stream error: %s", e, exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"
