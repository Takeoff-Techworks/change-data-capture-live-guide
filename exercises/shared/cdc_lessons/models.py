"""Exercise-owned source rows, CDC records, and read models."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SourceRecord(Base):
    __tablename__ = "source_records"
    source_table: Mapped[str] = mapped_column(primary_key=True)
    record_id: Mapped[str] = mapped_column(primary_key=True)
    patient_id: Mapped[str]
    payload_json: Mapped[str] = mapped_column(Text)


class RawCDCEvent(Base):
    __tablename__ = "raw_cdc_events"
    raw_event_id: Mapped[str] = mapped_column(primary_key=True)
    source_table: Mapped[str]
    payload_json: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CanonicalEvent(Base):
    __tablename__ = "canonical_events"
    event_id: Mapped[str] = mapped_column(primary_key=True)
    raw_event_id: Mapped[str] = mapped_column(unique=True)
    patient_id: Mapped[str]
    source_table: Mapped[str]
    operation: Mapped[str]
    entity_key_json: Mapped[str] = mapped_column(Text)
    source_commit_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(default="pending")


class CareWorkQueue(Base):
    __tablename__ = "care_work_queue"
    patient_id: Mapped[str] = mapped_column(primary_key=True)
    patient_display_name: Mapped[str]
    priority_score: Mapped[int]
    priority_reasons_json: Mapped[str] = mapped_column(Text)
    open_task_count: Mapped[int]
    overdue_task_count: Mapped[int]
    pending_referral_count: Mapped[int]
    latest_appointment_status: Mapped[str | None] = mapped_column(String, nullable=True)
    last_source_commit_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    projection_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventProcessingLog(Base):
    __tablename__ = "event_processing_log"
    event_id: Mapped[str] = mapped_column(primary_key=True)
    outcome: Mapped[str]
    message: Mapped[str]
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PatientTimeline(Base):
    __tablename__ = "patient_timeline"
    event_id: Mapped[str] = mapped_column(primary_key=True)
    patient_id: Mapped[str]
    event_type: Mapped[str]
    summary: Mapped[str]
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
