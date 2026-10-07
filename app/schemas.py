from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CanonicalChangeEvent(BaseModel):
    event_id: str
    source: Literal["simulated", "sqlserver", "postgres"]
    capture_method: Literal["simulated", "sqlserver_cdc", "debezium_postgres"]
    table: str
    operation: Literal["c", "u", "d"]
    entity_key: dict[str, str]
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    patient_id: str | None = None
    source_commit_at: datetime | None = None
    captured_at: datetime
    schema_version: int = 1
    correlation_id: str | None = None


class IngestPayload(BaseModel):
    payload: dict[str, Any]


class AssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    patient_id: str | None = None


class AssistantContext(BaseModel):
    persona_id: str
    facts: list[dict[str, Any]]
    freshness: datetime | None = None
    stale: bool = False


class AssistantAnswer(BaseModel):
    answer: str
    facts_used: list[dict[str, Any]]
    freshness: datetime | None = None
    may_be_stale: bool = False
