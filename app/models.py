from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    role: Mapped[str] = mapped_column(String)
    full_name: Mapped[str] = mapped_column(String)
    team_id: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Patient(Base):
    __tablename__ = "patients"
    patient_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    display_name: Mapped[str] = mapped_column(String)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contact_preference: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Provider(Base):
    __tablename__ = "providers"
    provider_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), unique=True)
    specialty: Mapped[str] = mapped_column(String)
    clinic_location: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Appointment(Base):
    __tablename__ = "appointments"
    appointment_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"))
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.provider_id"))
    scheduled_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String)
    reason_code: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Referral(Base):
    __tablename__ = "referrals"
    referral_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"))
    requested_by_provider_id: Mapped[str] = mapped_column(ForeignKey("providers.provider_id"))
    receiving_specialty: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scheduled_for_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CareTask(Base):
    __tablename__ = "care_tasks"
    task_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"))
    appointment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    referral_id: Mapped[str | None] = mapped_column(String, nullable=True)
    task_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    assigned_to_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[str] = mapped_column(String)
    priority_reason: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CareTeamAssignment(Base):
    __tablename__ = "care_team_assignments"
    assignment_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(255), unique=True)
    nurse_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_id: Mapped[str | None] = mapped_column(String, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RawCDCEvent(Base):
    __tablename__ = "raw_cdc_events"
    raw_event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    mode: Mapped[str] = mapped_column(String)
    source_table: Mapped[str] = mapped_column(String)
    payload_json: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CanonicalEvent(Base):
    __tablename__ = "canonical_events"
    __table_args__ = (
        Index(
            "uq_canonical_events_raw_event_id",
            "raw_event_id",
            unique=True,
            mssql_where=text("raw_event_id IS NOT NULL"),
        ),
    )
    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    raw_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String)
    capture_method: Mapped[str] = mapped_column(String)
    source_table: Mapped[str] = mapped_column(String)
    operation: Mapped[str] = mapped_column(String)
    entity_key_json: Mapped[str] = mapped_column(Text)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    patient_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_commit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    correlation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")


class EventProcessingLog(Base):
    __tablename__ = "event_processing_log"
    log_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(255))
    consumer_name: Mapped[str] = mapped_column(String(255))
    outcome: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("event_id", "consumer_name", name="uq_event_consumer"),)


class DeadLetterEvent(Base):
    __tablename__ = "dead_letter_events"
    dlq_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error_type: Mapped[str] = mapped_column(String)
    error_message: Mapped[str] = mapped_column(String)
    payload_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    replayed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CareWorkQueue(Base):
    __tablename__ = "care_work_queue"
    patient_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    patient_display_name: Mapped[str] = mapped_column(String)
    assigned_nurse_id: Mapped[str | None] = mapped_column(String, nullable=True)
    assigned_provider_id: Mapped[str | None] = mapped_column(String, nullable=True)
    latest_appointment_status: Mapped[str | None] = mapped_column(String, nullable=True)
    latest_appointment_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    open_task_count: Mapped[int] = mapped_column(Integer, default=0)
    overdue_task_count: Mapped[int] = mapped_column(Integer, default=0)
    oldest_open_task_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pending_referral_count: Mapped[int] = mapped_column(Integer, default=0)
    oldest_pending_referral_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    priority_score: Mapped[int] = mapped_column(Integer, default=0)
    priority_reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    last_source_commit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    projection_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PatientTimeline(Base):
    __tablename__ = "patient_timeline"
    timeline_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    patient_id: Mapped[str] = mapped_column(String)
    event_id: Mapped[str] = mapped_column(String(255), unique=True)
    event_type: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(String)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[str] = mapped_column(Text)


class PipelineState(Base):
    __tablename__ = "pipeline_state"
    consumer_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    mode: Mapped[str] = mapped_column(String)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    last_received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_successful_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pending_event_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_event_count: Mapped[int] = mapped_column(Integer, default=0)
    projection_freshness_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
