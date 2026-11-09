#!/usr/bin/env python3
"""Retention cleanup script for DPDP compliance.

Deletes evaluation records, messages, and orphaned conversations older than
CONVERSATION_RETENTION_DAYS (default: 90 days).

Defaults to --dry-run mode for safety. Pass --yes to execute deletions.
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.conversation import Conversation
from app.models.evaluation import EvaluationRecord
from app.models.message import Message

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def purge_old_records(
    db: AsyncSession,
    days: int = 90,
    dry_run: bool = True,
) -> dict[str, int]:
    """Identify and conditionally purge records older than the specified retention window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    logger.info("Purge cutoff timestamp (%d days): %s", days, cutoff.isoformat())

    # Count evaluation records
    eval_count_stmt = select(func.count(EvaluationRecord.id)).where(
        EvaluationRecord.created_at < cutoff
    )
    eval_count = (await db.execute(eval_count_stmt)).scalar() or 0

    # Count messages
    msg_count_stmt = select(func.count(Message.id)).where(
        Message.created_at < cutoff
    )
    msg_count = (await db.execute(msg_count_stmt)).scalar() or 0

    # Count conversations older than cutoff
    conv_count_stmt = select(func.count(Conversation.id)).where(
        Conversation.created_at < cutoff
    )
    conv_count = (await db.execute(conv_count_stmt)).scalar() or 0

    counts = {
        "evaluation_records": eval_count,
        "messages": msg_count,
        "conversations": conv_count,
    }

    if dry_run:
        logger.info(
            "DRY-RUN: Found %d evaluation records, %d messages, and %d conversations older than %d days. "
            "No data was deleted.",
            eval_count,
            msg_count,
            conv_count,
            days,
        )
        return counts

    # Execute actual deletions safely
    if eval_count > 0:
        await db.execute(
            delete(EvaluationRecord).where(EvaluationRecord.created_at < cutoff)
        )
    if msg_count > 0:
        await db.execute(
            delete(Message).where(Message.created_at < cutoff)
        )
    if conv_count > 0:
        await db.execute(
            delete(Conversation).where(Conversation.created_at < cutoff)
        )

    await db.commit()
    logger.info(
        "PURGE COMPLETE: Successfully deleted %d evaluation records, %d messages, and %d conversations.",
        eval_count,
        msg_count,
        conv_count,
    )
    return counts


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Purge old conversation and evaluation data for DPDP compliance."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=settings.CONVERSATION_RETENTION_DAYS,
        help=f"Retention period in days (default: {settings.CONVERSATION_RETENTION_DAYS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run without modifying database (default: True)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        default=False,
        help="Explicitly confirm deletion execution",
    )

    args = parser.parse_args()

    # Safety enforcement: require --yes to turn off dry-run
    execute_deletion = args.yes and not args.dry_run

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as db:
        await purge_old_records(
            db=db,
            days=args.days,
            dry_run=not execute_deletion,
        )


if __name__ == "__main__":
    asyncio.run(main())
