"""Admin API routes — protected by ADMIN_API_KEY."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import (
    get_embedding_provider,
    get_llm_provider,
    get_rag_service,
    verify_admin_key,
)
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.document import Document, DocumentVersion
from app.models.evaluation import EvaluationRecord
from app.models.feedback import Feedback
from app.models.message import Message
from app.providers.base import LLMProvider
from app.providers.embedding_base import EmbeddingProvider
from app.services.rag_service import RAGService
from app.schemas.admin import (
    AdminConversationDetailResponse,
    AdminConversationListResponse,
    AgentRunListResponse,
    CalculationScenarioListResponse,
    AdminStatsResponse,
    FeedbackItem,
    FeedbackListResponse,
    PromoteExemplarRequest,
    PromoteExemplarResponse,
)
from app.schemas.chat_settings import ChatSettingsResponse, ChatSettingsUpdate
from app.schemas.common import ErrorResponse
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.schemas.finance import FinanceCatalog
from app.schemas.lead import LeadListResponse, LeadResponse, LeadStatsResponse, LeadStatusUpdate
from app.services import (
    admin_service,
    agent_admin_service,
    calculation_admin_service,
    finance_service,
    lead_service,
)
from app.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _settings_response() -> ChatSettingsResponse:
    from app.services import app_settings

    return ChatSettingsResponse(
        settings=app_settings.current(),
        descriptions={k: f.description for k, f in app_settings.ChatSettings.model_fields.items()},
        updated_at=app_settings.meta().get("updated_at"))


@router.get("/settings", response_model=ChatSettingsResponse)
async def get_chat_settings(_admin: str = Depends(verify_admin_key)) -> ChatSettingsResponse:
    """The chat behaviour switches (concessions picker, counsellor connect, office hours)."""
    from app.services import app_settings

    await app_settings.refresh(force=True)
    return _settings_response()


@router.get("/videos")
async def admin_video_list(_admin: str = Depends(verify_admin_key)) -> dict:
    """Admin -> Campus media -> Videos (v4.14.0): every built-in official video (hidden ones too), the topics a
    video can be shown for, and the changes saved in the settings ("videos")."""
    from app.services import app_settings
    from app.services.video_service import load_videos

    await app_settings.refresh(force=True)
    keys = ("id", "title", "category", "type", "url", "thumbnail_url")
    return {"builtin": [{k: v.get(k) for k in keys} for v in load_videos()],
            "topics": list(app_settings.VIDEO_TOPICS), "changes": app_settings.get("videos")}


@router.post("/media")
async def upload_media(file: UploadFile = File(...), _admin: str = Depends(verify_admin_key)) -> dict:
    """Admin -> Campus media: upload an image for an ad or an event card (v4.15.1). Stored in the database (Render's
    disk does not keep files); returns the public path to put in `image_url`. JPEG / PNG / WebP only."""
    from app.services import media_store

    data = await file.read(media_store.MAX_BYTES + 1)
    try:
        return await media_store.save(data)
    except media_store.MediaError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.put("/settings", response_model=ChatSettingsResponse)
async def update_chat_settings(
    body: ChatSettingsUpdate,
    request: Request,
    _admin: str = Depends(verify_admin_key),
) -> ChatSettingsResponse:
    """Change chat behaviour switches. Takes effect for the next message; no redeploy needed."""
    from app import security
    from app.services import app_settings

    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Nothing to change.")
    try:
        await app_settings.update(changes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid setting: {exc}")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    security.audit(request, "chat_settings_update", "ok", changed=",".join(sorted(changes)))
    return _settings_response()


# ---- Talk to a counsellor (v4.12.0): requests ringing now, and "I'll call now" ----------------------------
@router.get("/live-requests")
async def get_live_requests(_admin: str = Depends(verify_admin_key)) -> dict:
    """Students waiting for a counsellor right now (each for up to the connect wait time)."""
    from app.services import live_connect

    return {"requests": await live_connect.waiting(), "in_office_hours": live_connect.in_office_hours()}


@router.post("/live-requests/{request_id}/accept")
async def accept_live_request(
    request_id: str,
    request: Request,
    counsellor: str | None = Query(None, max_length=40),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> dict:
    """A counsellor will call the student now. The first to accept wins."""
    from app import security
    from app.services import live_connect

    if not request_id.isalnum() or len(request_id) > 64:
        raise HTTPException(status_code=404, detail="Request not found.")
    outcome, req = await live_connect.accept(request_id, counsellor)
    security.audit(request, "live_request_accept", outcome)
    if outcome == "gone":
        raise HTTPException(status_code=404, detail="Request not found.")
    if outcome == "too_late":
        raise HTTPException(status_code=409, detail="This request has already been answered or timed out.")
    if req.get("lead_id"):
        try:
            await lead_service.update_lead_status(db, UUID(str(req["lead_id"])), "contacted")
        except Exception:
            logger.warning("Could not mark lead contacted after a live request was accepted")
    return {"status": "accepted", "phone": req["phone"], "first_name": req["first_name"], "case": req.get("case")}


# ---- Counsellor copilot (v4.12.0) ----------------------------------------------------------------------------
@router.get("/copilot/priorities")
async def copilot_priorities(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> dict:
    """Who to call first: open leads of the last 14 days, ranked, with the reasons."""
    from app.services import copilot_service

    return {"leads": await copilot_service.priorities(db, limit=limit)}


@router.get("/copilot/draft/{lead_id}")
async def copilot_draft(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> dict:
    """A draft follow-up message for one lead, written from its case summary. Nothing is sent."""
    from app.models.lead import ProspectiveLead
    from app.services import copilot_service

    lead = await db.get(ProspectiveLead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    return copilot_service.draft(lead)


@router.get("/agent-runs", response_model=AgentRunListResponse)
async def get_agent_runs(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> AgentRunListResponse:
    """List recent bounded-agent executions for operational review."""
    return await agent_admin_service.list_agent_runs(db, limit=limit)


@router.get("/calculations", response_model=CalculationScenarioListResponse)
async def get_calculations(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> CalculationScenarioListResponse:
    """List recent deterministic calculation scenarios for review."""
    return await calculation_admin_service.list_calculations(db, limit=limit)


@router.get("/finance-rules", response_model=FinanceCatalog)
async def get_finance_rules(
    _admin: str = Depends(verify_admin_key),
) -> FinanceCatalog:
    """Review the currently published fee and scholarship rules."""
    return finance_service.get_finance_catalog()


@router.put("/finance-rules", response_model=FinanceCatalog)
async def replace_finance_rules(
    catalog: FinanceCatalog,
    _admin: str = Depends(verify_admin_key),
) -> FinanceCatalog:
    """Publish a validated fee and scholarship catalog."""
    for rule in catalog.scholarship_rules:
        if rule.minimum_score_percent > rule.maximum_score_percent:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid score range for scholarship '{rule.name}'.",
            )
    return finance_service.replace_finance_catalog(catalog)


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={403: {"model": ErrorResponse}},
)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    document_type: str = Form(...),
    department: str | None = Form(None),
    effective_date: str | None = Form(None),
    publication_date: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    _admin: str = Depends(verify_admin_key),
) -> DocumentResponse:
    """Upload and ingest a document into the knowledge base.

    Requires `X-Admin-Key` header.
    """
    from datetime import datetime

    # Parse optional dates
    eff_date = None
    if effective_date:
        try:
            eff_date = datetime.fromisoformat(effective_date)
        except ValueError:
            raise HTTPException(400, "Invalid effective_date format. Use ISO 8601.")

    pub_date = None
    if publication_date:
        try:
            pub_date = datetime.fromisoformat(publication_date)
        except ValueError:
            raise HTTPException(400, "Invalid publication_date format. Use ISO 8601.")

    # Read file
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(400, "Empty file")

    # Size limit: 50MB
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(400, "File too large. Maximum size is 50MB.")

    try:
        ingestion = IngestionService(embeddings)
        doc = await ingestion.ingest_document(
            db=db,
            file_bytes=file_bytes,
            filename=file.filename or "unknown",
            title=title,
            document_type=document_type,
            department=department,
            effective_date=eff_date,
            publication_date=pub_date,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("Ingestion error: %s", e, exc_info=True)
        raise HTTPException(500, "Document ingestion failed. Check logs.")

    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        document_type=doc.document_type,
        department=doc.department,
        status=doc.status,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get(
    "/documents",
    response_model=DocumentListResponse,
)
async def list_documents(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> DocumentListResponse:
    """List all documents in the knowledge base."""
    stmt = select(Document).order_by(Document.created_at.desc())
    result = await db.execute(stmt)
    docs = result.scalars().all()

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=d.id,
                title=d.title,
                document_type=d.document_type,
                department=d.department,
                status=d.status,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d in docs
        ],
        total=len(docs),
    )


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> None:
    """Deactivate a document (soft delete)."""
    stmt = select(Document).where(Document.id == document_id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(404, "Document not found")

    doc.status = "inactive"

    # Also deactivate all versions
    ver_stmt = select(DocumentVersion).where(
        DocumentVersion.document_id == document_id
    )
    ver_result = await db.execute(ver_stmt)
    for version in ver_result.scalars().all():
        version.active = False


@router.get(
    "/stats",
    response_model=AdminStatsResponse,
)
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> AdminStatsResponse:
    """Get aggregate system statistics."""
    total_docs = await db.scalar(select(func.count(Document.id))) or 0
    active_docs = await db.scalar(select(func.count(Document.id)).where(Document.status == "active")) or 0
    total_convs = await db.scalar(select(func.count(Conversation.id))) or 0
    total_msgs = await db.scalar(select(func.count(Message.id))) or 0
    pos_feedback = await db.scalar(select(func.count(Feedback.id)).where(Feedback.rating == 1)) or 0
    neg_feedback = await db.scalar(select(func.count(Feedback.id)).where(Feedback.rating == -1)) or 0

    return AdminStatsResponse(
        total_documents=total_docs,
        active_documents=active_docs,
        total_conversations=total_convs,
        total_messages=total_msgs,
        positive_feedback=pos_feedback,
        negative_feedback=neg_feedback,
    )


@router.get(
    "/feedback",
    response_model=FeedbackListResponse,
)
async def list_admin_feedback(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> FeedbackListResponse:
    """List recent user feedback."""
    stmt = select(Feedback).order_by(Feedback.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    items = result.scalars().all()

    feedback_items = []
    for f in items:
        stmt_msg = select(Message).where(Message.id == f.message_id)
        res_msg = await db.execute(stmt_msg)
        msg = res_msg.scalar_one_or_none()
        answer = msg.content if msg else None

        question = None
        if msg:
            stmt_user = (
                select(Message)
                .where(
                    Message.conversation_id == msg.conversation_id,
                    Message.role == "user",
                    Message.created_at <= msg.created_at,
                )
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            res_user = await db.execute(stmt_user)
            user_msg = res_user.scalar_one_or_none()
            question = user_msg.content if user_msg else None

        feedback_items.append(
            FeedbackItem(
                id=f.id,
                session_id=f.session_id,
                conversation_id=f.conversation_id,
                message_id=f.message_id,
                rating=f.rating,
                comment=f.comment,
                question=question,
                answer=answer,
                created_at=f.created_at,
            )
        )

    return FeedbackListResponse(
        items=feedback_items,
        total=len(feedback_items),
    )


@router.get(
    "/conversations",
    response_model=AdminConversationListResponse,
)
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    search: str | None = Query(None),
    feedback_filter: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> AdminConversationListResponse:
    """List all user conversations with message metrics and feedback status."""
    return await admin_service.list_all_conversations(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        feedback_filter=feedback_filter,
    )


@router.get(
    "/conversations/export",
)
async def export_all_conversations(
    format: str = Query("markdown", pattern="^(markdown|json)$"),
    search: str | None = Query(None),
    feedback_filter: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> Response:
    """Export ALL student conversations into a single Markdown or JSON file for AI training and evaluation."""
    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if format == "json":
        content = await admin_service.export_all_conversations_json(
            db=db, search=search, feedback_filter=feedback_filter
        )
        media_type = "application/json"
        filename = f"university_ai_conversations_{timestamp}.json"
    else:
        content = await admin_service.export_all_conversations_markdown(
            db=db, search=search, feedback_filter=feedback_filter
        )
        media_type = "text/markdown"
        filename = f"university_ai_conversations_{timestamp}.md"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )



@router.get(
    "/conversations/{conversation_id}",
    response_model=AdminConversationDetailResponse,
)
async def get_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> AdminConversationDetailResponse:
    """Get complete conversation transcript with sources and feedback."""
    detail = await admin_service.get_conversation_detail(db, conversation_id)
    if detail is None:
        raise HTTPException(404, "Conversation not found")
    return detail


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> None:
    """Delete a conversation and all its messages."""
    deleted = await admin_service.delete_conversation_by_admin(db, conversation_id)
    if not deleted:
        raise HTTPException(404, "Conversation not found")


@router.post(
    "/exemplars/promote",
    response_model=PromoteExemplarResponse,
)
async def promote_exemplar(
    payload: PromoteExemplarRequest,
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    _admin: str = Depends(verify_admin_key),
) -> PromoteExemplarResponse:
    """Promote an approved Q&A to verified exemplars in ChromaDB for model improvement."""
    success = await admin_service.promote_qa_exemplar(
        embeddings=embeddings,
        message_id=payload.message_id,
        question=payload.question,
        answer=payload.answer,
    )
    if not success:
        raise HTTPException(500, "Failed to register verified exemplar in ChromaDB")
    return PromoteExemplarResponse(
        success=True,
        message="Successfully registered question-answer exemplar into ChromaDB.",
    )


@router.post("/evaluations/run")
async def run_evaluations(
    db: AsyncSession = Depends(get_db),
    rag: RAGService = Depends(get_rag_service),
    llm: LLMProvider = Depends(get_llm_provider),
    _admin: str = Depends(verify_admin_key),
):
    """Run benchmark evaluation suite against golden test cases."""
    from app.services.evaluation_service import run_benchmark_suite
    result = await run_benchmark_suite(db=db, rag_service=rag, llm_provider=llm)
    return result


@router.get("/evaluations")
async def list_evaluations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
):
    """List recent evaluation records."""
    offset = (page - 1) * page_size
    query = (
        select(EvaluationRecord)
        .order_by(EvaluationRecord.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    count_query = select(func.count(EvaluationRecord.id))

    total = (await db.execute(count_query)).scalar() or 0
    records = (await db.execute(query)).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "records": [
            {
                "id": str(r.id),
                "test_id": r.test_id,
                "category": r.category,
                "question": r.question,
                "expected_answer": r.expected_answer,
                "actual_answer": r.actual_answer,
                "groundedness_score": r.groundedness_score,
                "latency_ms": r.latency_ms,
                "passed": r.passed,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }


# ---- Prospective Leads & Admissions Inquiries ----

@router.get("/leads", response_model=LeadListResponse)
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    program: str | None = Query(None),
    source: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> LeadListResponse:
    """List prospective student leads with filtering, search, and pagination."""
    total, leads = await lead_service.list_leads(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        program=program,
        source=source,
        status=status,
    )
    return LeadListResponse(
        total=total,
        items=[LeadResponse.model_validate(l) for l in leads],
    )


@router.get("/leads/stats", response_model=LeadStatsResponse)
async def get_lead_stats(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> LeadStatsResponse:
    """Get aggregated lead statistics and conversion counts."""
    stats = await lead_service.get_lead_stats(db)
    return LeadStatsResponse(**stats)


@router.patch("/leads/{lead_id}/status", response_model=LeadResponse)
async def update_lead_status(
    lead_id: UUID,
    payload: LeadStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
) -> LeadResponse:
    """Update admissions status of a prospective lead."""
    updated = await lead_service.update_lead_status(db, lead_id, payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadResponse.model_validate(updated)


@router.get("/leads/export")
async def export_leads(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
):
    """Export all prospective leads as CSV for university admissions CRM matching."""
    import csv
    import io

    _, leads = await lead_service.list_leads(db=db, page=1, page_size=10000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID",
        "Name",
        "Phone",
        "Email",
        "Program Interest",
        "Score",
        "Exam Type",
        "Source",
        "Status",
        "Created At",
    ])
    for l in leads:
        writer.writerow([
            str(l.id),
            l.name,
            l.phone,
            l.email or "",
            l.program_interest or "",
            l.score or "",
            l.exam_type or "",
            l.source,
            l.status,
            l.created_at.isoformat() if l.created_at else "",
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sru_prospective_leads.csv"},
    )


@router.get("/telemetry")
async def get_telemetry(
    limit: int = Query(50, ge=1, le=500),
    _admin: str = Depends(verify_admin_key),
):
    """Return aggregated turn latency/token/cache observability metrics and recent turns."""
    from app.sru_agent import observability

    records = await observability.get_recent_telemetry_async(limit=limit)
    summary = observability.compute_telemetry_summary(records)
    return {
        "summary": summary,
        "recent": records[-limit:],
    }




