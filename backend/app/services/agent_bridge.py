"""Bridge callbacks wiring the SRU agent to PostgreSQL persistence, leads, and knowledge search."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_known_conversations: dict = {}    # (session_id, conversation_id) -> True, for this server process
_creating_conversations: dict = {}  # conversation_id -> task creating its database row


async def agent_lead_saver(lead_data: dict) -> dict:
    """Persist a lead from the agent tool call, waiting for any in-flight conversation creation."""
    from app.db.session import async_session_factory
    from app.schemas.lead import LeadCreate
    from app.services import lead_service

    lead_obj = LeadCreate(**lead_data)
    conv_id = lead_data.get("conversation_id")
    creating = _creating_conversations.get(str(conv_id)) if conv_id else None
    if creating is not None:
        try:
            await creating
        except Exception:
            pass
    async with async_session_factory() as session:
        created = await lead_service.create_lead(session, lead_obj)
        return {"id": str(created.id), "status": created.status}


async def agent_lead_canceller(lead_id: str, reason: str = "") -> bool:
    """Mark a lead as do-not-contact when requested by the student."""
    from app.db.session import async_session_factory
    from app.services import lead_service

    async with async_session_factory() as session:
        lead = await lead_service.cancel_lead(session, uuid.UUID(str(lead_id)), reason)
        return lead is not None


def _remember_conversation(session_id: str, conversation_id: str) -> None:
    if len(_known_conversations) > 20000:
        _known_conversations.clear()
    _known_conversations[(session_id, conversation_id)] = True


async def _create_conversation_row(session_id: str, conv_uuid, title: str) -> None:
    from app.db.session import async_session_factory
    from app.models.conversation import Conversation

    async with async_session_factory() as session:
        session.add(Conversation(id=conv_uuid, session_id=session_id, title=title))
        await session.commit()


async def agent_conversation_resolver(session_id: str, conversation_id: str | None, message: str) -> str:
    """Resolve or create a persistent conversation before streaming starts."""
    try:
        from app.sru_agent import config as agent_config, memory as agent_memory

        clean_title = (message or "").strip()
        if len(clean_title) > 50:
            clean_title = clean_title[:47].rstrip() + "..."
        if not clean_title:
            clean_title = "Chat"

        conv_uuid = None
        if conversation_id:
            try:
                conv_uuid = uuid.UUID(conversation_id)
            except (ValueError, TypeError):
                conv_uuid = None
        if conv_uuid and (session_id, str(conv_uuid)) in _known_conversations:
            return str(conv_uuid)

        if conv_uuid is None and agent_config.AGENT_LOCAL_CACHE and agent_config.AGENT_BACKGROUND_WRITES:
            new_id = uuid.uuid4()
            task = agent_memory.in_background(
                _create_conversation_row(session_id, new_id, clean_title), "conversation create"
            )
            if task is not None:
                _creating_conversations[str(new_id)] = task
                task.add_done_callback(lambda _t, k=str(new_id): _creating_conversations.pop(k, None))
                _remember_conversation(session_id, str(new_id))
                agent_memory.seed_new_conversation(session_id, str(new_id))
                return str(new_id)

        from app.db.session import async_session_factory
        from app.services import conversation_service

        async with async_session_factory() as session:
            conv = await conversation_service.get_or_create_conversation(
                session, session_id, conv_uuid, title=clean_title
            )
            await session.commit()
            if conv_uuid is None or conv.id != conv_uuid:
                agent_memory.seed_new_conversation(session_id, str(conv.id))
            _remember_conversation(session_id, str(conv.id))
            return str(conv.id)
    except Exception as err:
        logger.warning("agent_conversation_resolver error: %s", err)
        return conversation_id or ""


async def agent_turn_logger(
    session_id: str,
    conversation_id: str | None,
    user_text: str,
    answer: str,
    tools_used: list,
    cards: list | None = None,
    suggestions: list | None = None,
    started_at=None,
    channel: str | None = None,
    sources: list | None = None,
    message_id: str | None = None,
    user_message_id: str | None = None,
    user_metadata: dict | None = None,
    telemetry: dict | None = None,
) -> None:
    """Save one agent turn (user message, assistant answer, cards, sources, and optional telemetry)."""
    try:
        from app.db.session import async_session_factory
        from app.services import conversation_service
        from app.sru_agent import config as agent_config

        creating = _creating_conversations.get(str(conversation_id)) if conversation_id else None
        if creating is not None:
            try:
                await creating
            except Exception:
                pass

        async def _save(with_telemetry: bool) -> None:
            async with async_session_factory() as session:
                conv_uuid = uuid.UUID(conversation_id) if conversation_id else None
                clean_title = (user_text or "").strip()
                if len(clean_title) > 50:
                    clean_title = clean_title[:47].rstrip() + "..."
                conv = await conversation_service.get_or_create_conversation(
                    session, session_id, conv_uuid, title=clean_title
                )
                from app.sru_agent import intents as agent_intents
                if clean_title and not agent_intents.small_talk(user_text) and (
                    conv.title in ("New conversation", "Chat", "") or agent_intents.small_talk(conv.title)
                ):
                    conv.title = clean_title
                finished_at = datetime.now(timezone.utc)
                asked_at = started_at or finished_at
                if asked_at >= finished_at:
                    asked_at = finished_at - timedelta(milliseconds=1)

                await conversation_service.add_message(
                    session,
                    conv.id,
                    "user",
                    user_text,
                    created_at=asked_at,
                    metadata={k: v for k, v in (user_metadata or {}).items() if v} or None,
                    message_id=uuid.UUID(user_message_id) if user_message_id else None,
                )
                await conversation_service.add_message(
                    session,
                    conv.id,
                    "assistant",
                    answer,
                    model=agent_config.AGENT_MODEL,
                    metadata={
                        "tools_used": tools_used,
                        "cards": cards or [],
                        "suggestions": suggestions or [],
                        **({"channel": channel} if channel else {}),
                    },
                    sources=[
                        s for s in (sources or [])
                        if isinstance(s, dict) and s.get("document_id") and s.get("title")
                    ],
                    created_at=finished_at,
                    message_id=uuid.UUID(message_id) if message_id else None,
                )
                if with_telemetry:
                    from app.sru_agent import observability as agent_observability
                    session.add(agent_observability.build_turn_telemetry_row(telemetry))
                await session.commit()

        try:
            await _save(bool(telemetry))
        except Exception as err:
            if not telemetry:
                raise
            # Never lose the chat turn if telemetry fails (e.g. unmigrated table).
            logger.warning("turn telemetry not saved, saving the turn without it: %s", err)
            await _save(False)
    except Exception as err:
        logger.warning("agent_turn_logger error: %s", err)


def wire_agent_callbacks() -> None:
    """Register persistence, retrieval, and profile callbacks on the SRU agent."""
    from app.services import agent_profile_store
    from app.services.agent_knowledge_service import agent_knowledge_search
    from app.sru_agent import memory as agent_memory, tools as agent_tools
    from app.sru_agent.router import set_conversation_resolver, set_turn_logger

    set_turn_logger(agent_turn_logger)
    set_conversation_resolver(agent_conversation_resolver)
    agent_tools.set_knowledge_search(agent_knowledge_search)
    agent_tools.set_lead_saver(agent_lead_saver)
    agent_tools.set_lead_canceller(agent_lead_canceller)
    agent_tools.set_lead_updater(agent_profile_store.update_lead_contact)

    agent_memory.set_profile_store(agent_profile_store.load_profile, agent_profile_store.save_profile)
    agent_memory.set_history_loader(agent_profile_store.load_history)
    agent_memory.set_state_store(agent_profile_store.load_conversation_state, agent_profile_store.save_conversation_state)
