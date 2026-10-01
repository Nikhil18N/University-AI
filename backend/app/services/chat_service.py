"""Chat service — orchestrator for intent routing, query reformulation, and RAG."""

import logging
import random

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

GREETING_RESPONSES_INITIAL: list[str] = [
    "Hello! How can I help you today with SR University? Feel free to ask about admissions, programs, hostels, or campus life.",
    "Hi there! Great to chat with you. What would you like to know about SR University?",
    "Hey! Welcome to the SR University companion. What can I help you explore today?",
    "Hello! Looking for information on admissions, courses, placements, or facilities? Ask away!",
    "Hi! How can I assist you right now? Ask me anything about programs, campus events, hostels, or student life at SR University.",
    "Welcome! What's on your mind today regarding SR University?",
    "Hello! Good to see you. How can I assist with your SR University journey today?",
    "Hey there! Ready to help. What can I look up for you at SR University?",
]

GREETING_RESPONSES_FOLLOWUP: list[str] = [
    "Hey again! What else can I help you with?",
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
    "I'm doing well, thank you for asking! How can I assist you with SR University today?",
    "Doing great and ready to help! What would you like to know about SR University?",
    "I'm doing well, thanks! How can I help you with your queries today?",
]

HELP_RESPONSE: str = (
    "I'm here to assist you with everything at SR University! You can ask me about:\n\n"
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
    if intent == "GREETING":
        options = GREETING_RESPONSES_FOLLOWUP if has_context else GREETING_RESPONSES_INITIAL
        return random.choice(options)

    options = FAST_CONVERSATIONAL_RESPONSES.get(intent)
    if options:
        return random.choice(options)

    return "Hello! How can I help you today?"


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
        has_context = bool(conversation_context.strip())
        answer = get_conversational_response(intent, has_context=has_context)
        logger.info("Handled via fast conversational response (%s)", intent)

    elif intent == "UNIVERSITY" and rag_service:
        answer, sources = await rag_service.query(
            question=search_query,
            conversation_context=conversation_context,
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
