import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import CanonicalEvent, PipelineState, RawCDCEvent

from .normalizer import simulated_event


def capture_write(
    db: Session,
    table: str,
    operation: str,
    before: dict | None,
    after: dict | None,
    correlation_id: str,
) -> CanonicalEvent:
    raw_id = str(uuid4())
    raw = {
        "event_type": "simulated.row_change",
        "table": table,
        "operation": operation,
        "before": before,
        "after": after,
        "correlation_id": correlation_id,
    }
    db.add(
        RawCDCEvent(
            raw_event_id=raw_id,
            mode="simulated",
            source_table=table,
            payload_json=json.dumps(raw, default=str),
            received_at=datetime.now(UTC),
        )
    )
    event = simulated_event(table, operation, before, after, correlation_id)
    persisted = CanonicalEvent(
        event_id=event.event_id,
        raw_event_id=raw_id,
        source=event.source,
        capture_method=event.capture_method,
        source_table=event.table,
        operation=event.operation,
        entity_key_json=json.dumps(event.entity_key),
        before_json=json.dumps(event.before, default=str) if event.before else None,
        after_json=json.dumps(event.after, default=str) if event.after else None,
        patient_id=event.patient_id,
        source_commit_at=event.source_commit_at,
        captured_at=event.captured_at,
        schema_version=event.schema_version,
        correlation_id=correlation_id,
        status="pending",
    )
    db.add(persisted)
    state = db.get(PipelineState, "projection-consumer")
    if not state:
        state = PipelineState(consumer_name="projection-consumer", mode="simulated", paused=False)
        db.add(state)
    state.last_received_at = datetime.now(UTC)
    db.flush()
    return persisted
