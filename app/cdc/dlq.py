import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import DeadLetterEvent


def write_dlq(
    db: Session, event_id: str | None, raw_event_id: str | None, error: Exception, payload: object
) -> DeadLetterEvent:
    item = DeadLetterEvent(
        dlq_id=str(uuid4()),
        event_id=event_id,
        raw_event_id=raw_event_id,
        error_type=type(error).__name__,
        error_message=str(error),
        payload_json=json.dumps(payload, default=str),
        status="open",
        created_at=datetime.now(UTC),
    )
    db.add(item)
    return item
