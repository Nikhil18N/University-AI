"""Admin API routes — protected by ADMIN_API_KEY."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_embedding_provider, verify_admin_key
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.document import Document, DocumentVersion
from app.models.feedback import Feedback
from app.models.message import Message
from app.providers.embedding_base import EmbeddingProvider
from app.schemas.admin import AdminStatsResponse, FeedbackItem, FeedbackListResponse
from app.schemas.common import ErrorResponse
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


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

    return FeedbackListResponse(
        items=[
            FeedbackItem(
                id=f.id,
                session_id=f.session_id,
                conversation_id=f.conversation_id,
                message_id=f.message_id,
                rating=f.rating,
                comment=f.comment,
                created_at=f.created_at,
            )
            for f in items
        ],
        total=len(items),
    )
