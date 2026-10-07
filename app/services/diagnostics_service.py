import json

from sqlalchemy import select

from app.cdc.consumer import refresh_state
from app.models import (
    CanonicalEvent,
    CareWorkQueue,
    EventProcessingLog,
    PatientTimeline,
    RawCDCEvent,
)


def health(db):
    state = refresh_state(db)
    db.commit()
    return {
        "mode": state.mode,
        "consumer_state": "paused" if state.paused else "running",
        "pending_events": state.pending_event_count,
        "failed_events": state.failed_event_count,
        "projection_freshness_at": state.projection_freshness_at,
        "adapter_label": "Simulated local adapter"
        if state.mode == "simulated"
        else (
            "SQL Server adapter fixture/ingestion mode"
            if state.mode == "sqlserver"
            else "PostgreSQL + Debezium fixture/ingestion mode"
        ),
    }


def trace(db, event_id: str):
    event = db.get(CanonicalEvent, event_id)
    if not event:
        return None
    raw = db.get(RawCDCEvent, event.raw_event_id) if event.raw_event_id else None
    logs = list(
        db.scalars(select(EventProcessingLog).where(EventProcessingLog.event_id == event_id))
    )
    timeline = db.scalar(select(PatientTimeline).where(PatientTimeline.event_id == event_id))
    queue = db.get(CareWorkQueue, event.patient_id) if event.patient_id else None
    return {
        "event": {
            "event_id": event.event_id,
            "source_table": event.source_table,
            "operation": event.operation,
            "status": event.status,
            "before": json.loads(event.before_json) if event.before_json else None,
            "after": json.loads(event.after_json) if event.after_json else None,
        },
        "raw_payload": json.loads(raw.payload_json) if raw else None,
        "processing_logs": [{"outcome": x.outcome, "message": x.message} for x in logs],
        "timeline": timeline.summary if timeline else None,
        "projection": {
            "priority_score": queue.priority_score,
            "open_task_count": queue.open_task_count,
        }
        if queue
        else None,
    }
