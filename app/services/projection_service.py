import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Appointment,
    CanonicalEvent,
    CareTask,
    CareTeamAssignment,
    CareWorkQueue,
    Patient,
    PatientTimeline,
    Referral,
)


def score(tasks, referrals, latest_appointment):
    now = datetime.now(UTC)

    def aware(value):
        return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value

    reasons, value = [], 0
    if any(aware(t.due_at) and aware(t.due_at) < now for t in tasks):
        value += 50
        reasons.append("Open task overdue (+50)")
    if any(
        r.status in {"requested", "pending"} and aware(r.requested_at) < now - timedelta(days=7)
        for r in referrals
    ):
        value += 30
        reasons.append("Referral pending more than 7 days (+30)")
    if (
        latest_appointment
        and latest_appointment.status == "no_show"
        and not any(t.task_type == "reschedule" for t in tasks)
    ):
        value += 20
        reasons.append("No-show has no active reschedule task (+20)")
    if any(aware(t.due_at) and now <= aware(t.due_at) <= now + timedelta(hours=24) for t in tasks):
        value += 10
        reasons.append("Open task due within 24 hours (+10)")
    return value, reasons


def recompute_patient(db: Session, patient_id: str, event: CanonicalEvent) -> CareWorkQueue | None:
    patient = db.get(Patient, patient_id)
    if not patient:
        return None
    now = datetime.now(UTC)
    assignment = db.scalar(
        select(CareTeamAssignment).where(CareTeamAssignment.patient_id == patient_id)
    )
    appointments = list(
        db.scalars(
            select(Appointment)
            .where(Appointment.patient_id == patient_id)
            .order_by(Appointment.scheduled_start_at.desc())
        )
    )
    tasks = list(
        db.scalars(
            select(CareTask).where(
                CareTask.patient_id == patient_id, CareTask.status.in_(["open", "in_progress"])
            )
        )
    )
    referrals = list(
        db.scalars(
            select(Referral).where(
                Referral.patient_id == patient_id, Referral.status.in_(["requested", "pending"])
            )
        )
    )
    latest = appointments[0] if appointments else None
    priority, reasons = score(tasks, referrals, latest)
    row = db.get(CareWorkQueue, patient_id) or CareWorkQueue(
        patient_id=patient_id, patient_display_name=patient.display_name, projection_updated_at=now
    )
    row.patient_display_name, row.assigned_nurse_id, row.assigned_provider_id = (
        patient.display_name,
        assignment.nurse_user_id if assignment else None,
        assignment.provider_id if assignment else None,
    )
    row.latest_appointment_status, row.latest_appointment_at = (
        (latest.status, latest.scheduled_start_at) if latest else (None, None)
    )
    aware = lambda value: value.replace(tzinfo=UTC) if value and value.tzinfo is None else value
    row.open_task_count, row.overdue_task_count = (
        len(tasks),
        sum(bool(aware(t.due_at) and aware(t.due_at) < now) for t in tasks),
    )
    row.oldest_open_task_due_at = min((aware(t.due_at) for t in tasks if t.due_at), default=None)
    row.pending_referral_count, row.oldest_pending_referral_at = (
        len(referrals),
        min((r.requested_at for r in referrals), default=None),
    )
    (
        row.priority_score,
        row.priority_reasons_json,
        row.last_source_commit_at,
        row.projection_updated_at,
    ) = priority, json.dumps(reasons), event.source_commit_at, now
    db.add(row)
    if not db.get(PatientTimeline, event.event_id):
        db.add(
            PatientTimeline(
                timeline_id=str(uuid4()),
                patient_id=patient_id,
                event_id=event.event_id,
                event_type=f"{event.source_table}.{event.operation}",
                summary=f"{event.source_table} {event.operation} processed for administrative coordination",
                occurred_at=event.source_commit_at or now,
                metadata_json=json.dumps(
                    {
                        "correlation_id": event.correlation_id,
                        "entity_key": json.loads(event.entity_key_json),
                    }
                ),
            )
        )
    return row
