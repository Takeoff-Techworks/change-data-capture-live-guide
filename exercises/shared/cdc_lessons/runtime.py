"""Seed an isolated database and simulate source writes flowing through CDC."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from .models import (
    Base,
    CanonicalEvent,
    CareWorkQueue,
    EventProcessingLog,
    PatientTimeline,
    RawCDCEvent,
    SourceRecord,
)


def _now():
    return datetime.now(UTC)


def _project(db: Session, event: CanonicalEvent) -> None:
    records = list(
        db.scalars(select(SourceRecord).where(SourceRecord.patient_id == event.patient_id))
    )
    patient = next(json.loads(r.payload_json) for r in records if r.source_table == "patients")
    tasks = [json.loads(r.payload_json) for r in records if r.source_table == "care_tasks"]
    referrals = [json.loads(r.payload_json) for r in records if r.source_table == "referrals"]
    open_tasks = [t for t in tasks if t["status"] in {"open", "in_progress"}]
    overdue = [t for t in open_tasks if datetime.fromisoformat(t["due_at"]) < _now()]
    pending = [r for r in referrals if r["status"] in {"requested", "pending"}]
    reasons = []
    if overdue:
        reasons.append("Open task overdue (+50)")
    if pending:
        reasons.append("Pending referral (+30)")
    row = db.get(CareWorkQueue, event.patient_id)
    if row is None:
        row = CareWorkQueue(patient_id=event.patient_id)
        db.add(row)
    row.patient_display_name = patient["display_name"]
    row.open_task_count = len(open_tasks)
    row.overdue_task_count = len(overdue)
    row.pending_referral_count = len(pending)
    row.latest_appointment_status = "scheduled"
    row.priority_score = 50 * bool(overdue) + 30 * bool(pending)
    row.priority_reasons_json = json.dumps(reasons)
    row.last_source_commit_at = event.source_commit_at
    row.projection_updated_at = _now()
    event.status = "processed"
    db.add(
        EventProcessingLog(
            event_id=event.event_id,
            outcome="processed",
            message="Updated care_work_queue and patient_timeline",
            processed_at=_now(),
        )
    )
    db.add(
        PatientTimeline(
            event_id=event.event_id,
            patient_id=event.patient_id,
            event_type=f"{event.source_table}.{event.operation}",
            summary=f"{event.source_table} changed; priority is now {row.priority_score}",
            occurred_at=_now(),
        )
    )


def _capture(db: Session, record: SourceRecord, before: dict | None) -> str:
    committed_at = _now()
    correlation_id = str(uuid4())
    raw_id = str(uuid4())
    payload = {
        "before": before,
        "after": json.loads(record.payload_json),
        "operation": "c" if before is None else "u",
        "source_commit_at": committed_at.isoformat(),
        "correlation_id": correlation_id,
    }
    db.add(
        RawCDCEvent(
            raw_event_id=raw_id,
            source_table=record.source_table,
            payload_json=json.dumps(payload),
            received_at=_now(),
        )
    )
    event = CanonicalEvent(
        event_id=str(uuid4()),
        raw_event_id=raw_id,
        patient_id=record.patient_id,
        source_table=record.source_table,
        operation=payload["operation"],
        entity_key_json=json.dumps({"record_id": record.record_id}),
        source_commit_at=committed_at,
        captured_at=_now(),
        status="pending",
    )
    db.add(event)
    db.flush()
    _project(db, event)
    db.commit()
    return correlation_id


def create_lesson_db(database_url: str = "sqlite:///:memory:") -> Session:
    """Seed a fresh exercise database, in memory unless a SQLite URL is supplied."""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    db = Session(engine)
    for patient_id, name in [("p2", "Morgan Lee"), ("p3", "Alex Chen"), ("p4", "Sam Rivera")]:
        db.add(
            SourceRecord(
                source_table="patients",
                record_id=patient_id,
                patient_id=patient_id,
                payload_json=json.dumps({"display_name": name}),
            )
        )
    db.add(
        SourceRecord(
            source_table="care_tasks",
            record_id="task1",
            patient_id="p2",
            payload_json=json.dumps(
                {
                    "status": "open",
                    "task_type": "reschedule",
                    "due_at": (_now() - timedelta(days=1)).isoformat(),
                }
            ),
        )
    )
    db.add(
        SourceRecord(
            source_table="referrals",
            record_id="ref2",
            patient_id="p4",
            payload_json=json.dumps({"status": "pending", "scheduled_for_at": None}),
        )
    )
    db.flush()
    for record in list(
        db.scalars(select(SourceRecord).where(SourceRecord.source_table == "patients"))
    ):
        _capture(db, record, before=None)
    return db


def _update(db: Session, table: str, record_id: str, changes: dict) -> str:
    record = db.get(SourceRecord, (table, record_id))
    if record is None:
        raise ValueError(f"Unknown {table} record: {record_id}")
    before = json.loads(record.payload_json)
    record.payload_json = json.dumps({**before, **changes})
    return _capture(db, record, before)


def update_task(db: Session, task_id: str, status: str) -> str:
    return _update(db, "care_tasks", task_id, {"status": status})


def update_referral(
    db: Session, referral_id: str, status: str, scheduled_for_at: datetime | None = None
) -> str:
    return _update(
        db,
        "referrals",
        referral_id,
        {
            "status": status,
            "scheduled_for_at": scheduled_for_at.isoformat() if scheduled_for_at else None,
        },
    )
