from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from app.cdc.consumer import process_pending
from app.cdc.simulated import capture_write
from app.config import settings
from app.models import Appointment, CareTask, Referral


def row_dict(item) -> dict:
    return {
        c.key: (
            getattr(item, c.key).isoformat()
            if isinstance(getattr(item, c.key), datetime)
            else getattr(item, c.key)
        )
        for c in inspect(item).mapper.column_attrs
    }


def emit(db: Session, table: str, operation: str, before: dict | None, after: dict | None) -> str:
    correlation_id = str(uuid4())
    capture_write(db, table, operation, before, after, correlation_id)
    db.commit()
    if settings.auto_process:
        process_pending(db)
    return correlation_id


def create_appointment(
    db: Session,
    patient_id: str,
    provider_id: str,
    scheduled_start_at: datetime,
    reason_code: str | None = None,
) -> tuple[Appointment, str]:
    item = Appointment(
        appointment_id=str(uuid4()),
        patient_id=patient_id,
        provider_id=provider_id,
        scheduled_start_at=scheduled_start_at,
        status="scheduled",
        reason_code=reason_code,
        updated_at=datetime.now(UTC),
    )
    db.add(item)
    db.flush()
    return item, emit(db, "appointments", "c", None, row_dict(item))


def update_appointment(
    db: Session,
    appointment_id: str,
    status: str | None = None,
    scheduled_start_at: datetime | None = None,
    reason_code: str | None = None,
    create_follow_up: bool = False,
) -> str:
    item = db.get(Appointment, appointment_id)
    if not item:
        raise ValueError("Appointment not found")
    before = row_dict(item)
    if status:
        item.status = status
    if scheduled_start_at:
        item.scheduled_start_at = scheduled_start_at
    if reason_code is not None:
        item.reason_code = reason_code
    item.updated_at = datetime.now(UTC)
    db.flush()
    correlation = emit(db, "appointments", "u", before, row_dict(item))
    if status == "no_show" and not db.scalar(
        select(CareTask).where(
            CareTask.appointment_id == item.appointment_id,
            CareTask.task_type == "reschedule",
            CareTask.status.in_(["open", "in_progress"]),
        )
    ):
        create_task(
            db,
            item.patient_id,
            "reschedule",
            "nurse-a",
            datetime.now(UTC),
            appointment_id=item.appointment_id,
        )
    if status == "completed" and create_follow_up:
        create_task(db, item.patient_id, "follow_up", "nurse-a", datetime.now(UTC))
    return correlation


def create_task(
    db: Session,
    patient_id: str,
    task_type: str,
    assigned_to: str | None,
    due_at: datetime | None,
    appointment_id: str | None = None,
    referral_id: str | None = None,
) -> tuple[CareTask, str]:
    item = CareTask(
        task_id=str(uuid4()),
        patient_id=patient_id,
        appointment_id=appointment_id,
        referral_id=referral_id,
        task_type=task_type,
        status="open",
        assigned_to_user_id=assigned_to,
        due_at=due_at,
        priority="normal",
        priority_reason="demo workflow",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(item)
    db.flush()
    return item, emit(db, "care_tasks", "c", None, row_dict(item))


def update_task(
    db: Session, task_id: str, status: str | None = None, assigned_to: str | None = None
) -> str:
    item = db.get(CareTask, task_id)
    if not item:
        raise ValueError("Task not found")
    before = row_dict(item)
    item.status = status or item.status
    item.assigned_to_user_id = assigned_to if assigned_to is not None else item.assigned_to_user_id
    item.updated_at = datetime.now(UTC)
    db.flush()
    return emit(db, "care_tasks", "u", before, row_dict(item))


def create_referral(
    db: Session, patient_id: str, provider_id: str, specialty: str
) -> tuple[Referral, str]:
    item = Referral(
        referral_id=str(uuid4()),
        patient_id=patient_id,
        requested_by_provider_id=provider_id,
        receiving_specialty=specialty,
        status="requested",
        requested_at=datetime.now(UTC),
        scheduled_for_at=None,
        updated_at=datetime.now(UTC),
    )
    db.add(item)
    db.flush()
    return item, emit(db, "referrals", "c", None, row_dict(item))


def update_referral(
    db: Session, referral_id: str, status: str, scheduled_for_at: datetime | None = None
) -> str:
    item = db.get(Referral, referral_id)
    if not item:
        raise ValueError("Referral not found")
    before = row_dict(item)
    item.status = status
    item.scheduled_for_at = scheduled_for_at
    item.updated_at = datetime.now(UTC)
    db.flush()
    return emit(db, "referrals", "u", before, row_dict(item))
