"""Chat service — orchestrator for intent routing, query reformulation, and RAG."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.providers.base import LLMProvider
from app.services import conversation_service, prompt_service
from app.services.intent_service import classify_intent
from app.services.reformulation_service import needs_reformulation, reformulate_query
from app.services.rag_service import RAGService
from app.schemas.chat import ChatRequest, ChatResponse, SourceReference

logger = logging.getLogger(__name__)

STUDENT_AUTH_MESSAGE = (
    "To access personal student records such as your attendance, grades, GPA, "
    "individual fee dues, or personal timetable, please log in to the student "
    "portal at https://portal.university.edu using your student credentials. "
    "In anonymous public mode, I do not have access to individual student records."
)

FAST_CONVERSATIONAL_RESPONSES: dict[str, str] = {
    "GREETING": (
        "Hello! I'm your SR University AI Companion. How can I help you today? "
        "Feel free to ask about admissions, programs, labs, hostels, placements, or campus facilities!"
    ),
    "ACKNOWLEDGMENT": (
        "Glad to help! Let me know if you have any other questions about SR University."
    ),
    "THANKS": (
        "You're very welcome! If there's anything else you'd like to know about SR University, feel free to ask."
    ),
    "GOODBYE": (
        "Goodbye! Best of luck with your academic journey at SR University. Have a wonderful day!"
    ),
    "HOW_ARE_YOU": (
        "I'm doing well, thank you for asking! How can I assist you with SR University today?"
    ),
    "HELP": (
        "I'm here to assist you with everything at SR University! You can ask me about:\n\n"
        "• **Admissions & Eligibility**: Application process, requirements, and deadlines\n"
        "• **Academics & Labs**: Programs, departments, curriculum, and modern lab facilities\n"
        "• **Campus & Hostels**: Accommodation details, mess, transport, and campus amenities\n"
        "• **Placements & Innovation**: Career opportunities, campus placements, and SRiX incubator\n\n"
        "What would you like to explore?"
    ),
}


async def handle_chat(
    db: AsyncSession,
    request: ChatRequest,
    llm_provider: LLMProvider,
    rag_service: RAGService | None = None,
) -> ChatResponse:
    """Process a chat message and return a response.

    Orchestration:
    1. Get or create conversation
    2. Save user message
    3. Build context from recent messages
    4. Classify intent (hybrid fast filter + LLM classifier)
    5. Route:
       - STUDENT_SPECIFIC: auth guardrail guidance
       - UNIVERSITY: contextual reformulation → RAG pipeline
       - GENERAL / GREETING: conversational LLM
    6. Save assistant message
    7. Auto-title conversation on first exchange
    8. Return response
    """
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
        f"{m['role']}: {m['content']}" for m in recent[:-1]  # exclude current message
    )

    # 4. Classify intent on the RAW message first — before any reformulation.
    #    This ensures greetings/chitchat are never accidentally routed to RAG
    #    even when there is prior university conversation context.
    intent, confidence = await classify_intent(
        request.message,
        conversation_context=conversation_context,
        llm_provider=llm_provider,
    )
    logger.info(
        "Message '%s...' classified as %s (confidence=%.2f)",
        request.message[:30], intent, confidence,
    )

    # 5. Contextual query reformulation — ONLY for university queries.
    #    Skipping reformulation for greetings/chitchat prevents "hi" from
    #    being expanded into the previous topic and misrouted to RAG.
    search_query = request.message
    if intent == "UNIVERSITY":
        is_follow_up = needs_reformulation(request.message, conversation_context)
        if is_follow_up:
            search_query = await reformulate_query(
                request.message,
                conversation_context=conversation_context,
                llm_provider=llm_provider,
            )

    # 6. Route and generate response
    sources: list[dict] = []

    if intent == "STUDENT_SPECIFIC":
        # Guest mode guardrail: Personal student data requires portal login
        answer = STUDENT_AUTH_MESSAGE
        logger.info("Handled via STUDENT_SPECIFIC auth guardrail")

    elif intent in FAST_CONVERSATIONAL_RESPONSES:
        answer = FAST_CONVERSATIONAL_RESPONSES[intent]
        logger.info("Handled via fast conversational response (%s)", intent)

    elif intent == "UNIVERSITY" and rag_service:
        answer, sources = await rag_service.query(
            question=search_query,
            conversation_context=conversation_context if is_follow_up else "",
        )
        logger.info("Handled via RAG pipeline (search query: '%s')", search_query[:50])

    else:
        # General conversation / open-ended → conversational LLM
        system_prompt = prompt_service.load_prompt("system")
        messages = [{"role": "system", "content": system_prompt}] + recent
        answer = await llm_provider.generate(messages)
        logger.info("Handled via conversational LLM (%s)", intent)

    # 6. Save assistant message
    assistant_msg = await conversation_service.add_message(
        db,
        conversation.id,
        role="assistant",
        content=answer,
        model=settings.LLM_MODEL,
        sources=sources if sources else None,
    )

    # 7. Auto-title on first exchange
    if conversation.title == "New conversation":
        title = request.message[:50].strip()
        if len(request.message) > 50:
            title += "..."
        await conversation_service.update_conversation_title(
            db, conversation.id, title
        )

    # 8. Return response
    return ChatResponse(
        conversation_id=conversation.id,
        message_id=assistant_msg.id,
        answer=answer,
        sources=[SourceReference(**s) for s in sources] if sources else [],
        model=settings.LLM_MODEL,
    )
