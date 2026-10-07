from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CanonicalEvent, EventProcessingLog, PipelineState
from app.services.projection_service import recompute_patient

from .dlq import write_dlq

CONSUMER = "projection-consumer"


def state(db: Session) -> PipelineState:
    item = db.get(PipelineState, CONSUMER)
    if not item:
        item = PipelineState(
            consumer_name=CONSUMER, mode=settings.cdc_mode, paused=settings.consumer_paused
        )
        db.add(item)
        db.flush()
    return item


def _log(db: Session, event_id: str, outcome: str, message: str) -> None:
    db.add(
        EventProcessingLog(
            log_id=str(uuid4()),
            event_id=event_id,
            consumer_name=CONSUMER,
            outcome=outcome,
            message=message,
            processed_at=datetime.now(UTC),
        )
    )


def refresh_state(db: Session) -> PipelineState:
    item = state(db)
    item.pending_event_count = (
        db.scalar(
            select(func.count())
            .select_from(CanonicalEvent)
            .where(CanonicalEvent.status == "pending")
        )
        or 0
    )
    item.failed_event_count = (
        db.scalar(
            select(func.count())
            .select_from(CanonicalEvent)
            .where(CanonicalEvent.status.in_(["failed", "dead_lettered"]))
        )
        or 0
    )
    return item


def process_pending(db: Session, limit: int | None = None) -> int:
    item = state(db)
    if item.paused:
        return 0
    events = list(
        db.scalars(
            select(CanonicalEvent)
            .where(CanonicalEvent.status == "pending")
            .order_by(CanonicalEvent.captured_at)
            .limit(limit)
        )
    )
    completed = 0
    for event in events:
        existing = db.scalar(
            select(EventProcessingLog).where(
                EventProcessingLog.event_id == event.event_id,
                EventProcessingLog.consumer_name == CONSUMER,
                EventProcessingLog.outcome == "processed",
            )
        )
        if existing:
            event.status = "duplicate"
            _log(db, event.event_id, "duplicate_skipped", "Already applied by projection consumer")
            continue
        try:
            if settings.failure_mode == "projection_once":
                raise RuntimeError("Injected one-time projection failure")
            if (
                settings.failure_mode.startswith("always_fail_table:")
                and settings.failure_mode.split(":", 1)[1] == event.source_table
            ):
                raise RuntimeError(f"Injected failure for {event.source_table}")
            if event.patient_id:
                recompute_patient(db, event.patient_id, event)
            event.status = "processed"
            _log(db, event.event_id, "processed", "Projection recomputed from source records")
            item.last_processed_at = datetime.now(UTC)
            item.last_successful_event_id = event.event_id
            item.projection_freshness_at = item.last_processed_at
            completed += 1
        except Exception as exc:
            event.status = "dead_lettered"
            write_dlq(
                db,
                event.event_id,
                event.raw_event_id,
                exc,
                {"before": event.before_json, "after": event.after_json},
            )
        finally:
            if settings.failure_mode == "projection_once":
                object.__setattr__(settings, "failure_mode", "none")
    refresh_state(db)
    db.commit()
    return completed


def duplicate_event(db: Session, event_id: str) -> CanonicalEvent:
    original = db.get(CanonicalEvent, event_id)
    if not original:
        raise ValueError("Event not found")
    copy = CanonicalEvent(
        event_id=str(uuid4()),
        raw_event_id=None,
        source=original.source,
        capture_method=original.capture_method,
        source_table=original.source_table,
        operation=original.operation,
        entity_key_json=original.entity_key_json,
        before_json=original.before_json,
        after_json=original.after_json,
        patient_id=original.patient_id,
        source_commit_at=original.source_commit_at,
        captured_at=datetime.now(UTC),
        schema_version=original.schema_version,
        correlation_id=original.correlation_id,
        status="pending",
    )
    db.add(copy)
    db.commit()
    return copy
