"""Read-only, allowlisted tools over the exercise projection and history."""

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .context_store import build_context_store, evaluate_freshness
from .models import CareWorkQueue, PatientTimeline

#: Entities an agent is allowed to discover and read. Anything else --
#: including the real source tables -- is denied by name.
ALLOWED_ENTITIES: dict[str, dict[str, Any]] = {
    "care_work_queue": {
        "description": "Bounded, CDC-maintained agent-facing projection of care coordination status.",
        "fields": [
            "patient_id",
            "patient_display_name",
            "priority_score",
            "priority_reasons",
            "open_task_count",
            "overdue_task_count",
            "pending_referral_count",
            "latest_appointment_status",
            "projection_updated_at",
        ],
    },
    "patient_timeline": {
        "description": "CDC-derived change history entries for a patient's coordination record.",
        "fields": ["event_id", "event_type", "summary", "occurred_at"],
    },
}

#: Read-only tool names an agent may invoke. Anything else (updates,
#: deletes, arbitrary SQL) is refused explicitly.
ALLOWED_TOOLS = {
    "list_entities",
    "get_record",
    "search_records",
    "get_change_history",
    "get_freshness_status",
}

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "list_entities": {
        "description": "List allowlisted, read-only entities exposed by this gateway.",
        "parameters": {"type": "object", "properties": {}},
    },
    "get_record": {
        "description": "Bounded lookup of a single record by id from an allowlisted entity.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "enum": list(ALLOWED_ENTITIES)},
                "record_id": {"type": "string"},
                "fields": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["entity", "record_id"],
        },
    },
    "search_records": {
        "description": "Bounded search over an allowlisted entity (result count is capped).",
        "parameters": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "enum": list(ALLOWED_ENTITIES)},
                "min_priority_score": {"type": "integer"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["entity"],
        },
    },
    "get_change_history": {
        "description": "CDC-derived change history for a record, most recent first.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "enum": list(ALLOWED_ENTITIES)},
                "record_id": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["entity", "record_id"],
        },
    },
    "get_freshness_status": {
        "description": "Freshness metadata and policy decision for a record's context entry.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "enum": list(ALLOWED_ENTITIES)},
                "record_id": {"type": "string"},
                "budget_seconds": {"type": "number", "default": 300},
            },
            "required": ["entity", "record_id"],
        },
    },
}

MAX_SEARCH_LIMIT = 25


@dataclass
class ToolResult:
    tool: str
    allowed: bool
    denial_reason: str | None = None
    data: Any = None
    evidence_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "allowed": self.allowed,
            "denial_reason": self.denial_reason,
            "data": self.data,
            "evidence_ids": self.evidence_ids,
        }


def _deny(tool: str, reason: str) -> ToolResult:
    return ToolResult(tool=tool, allowed=False, denial_reason=reason, data=None, evidence_ids=[])


def list_entities() -> ToolResult:
    return ToolResult(
        tool="list_entities",
        allowed=True,
        data=[{"entity": name, **meta} for name, meta in ALLOWED_ENTITIES.items()],
        evidence_ids=list(ALLOWED_ENTITIES),
    )


def get_record(
    db: Session, entity: str, record_id: str, fields: list[str] | None = None
) -> ToolResult:
    if entity not in ALLOWED_ENTITIES:
        return _deny(
            "get_record",
            f"Entity '{entity}' is not exposed by this gateway; agents do not query the "
            "production/source store directly.",
        )
    allowed_fields = ALLOWED_ENTITIES[entity]["fields"]
    if fields:
        unapproved = [f for f in fields if f not in allowed_fields]
        if unapproved:
            return _deny(
                "get_record",
                f"Field(s) {unapproved} are not approved for entity '{entity}'.",
            )
    if entity == "care_work_queue":
        row = db.get(CareWorkQueue, record_id)
        if not row:
            return _deny("get_record", f"No care_work_queue record for id '{record_id}'.")
        record = {
            "patient_id": row.patient_id,
            "patient_display_name": row.patient_display_name,
            "priority_score": row.priority_score,
            "priority_reasons": json.loads(row.priority_reasons_json),
            "open_task_count": row.open_task_count,
            "overdue_task_count": row.overdue_task_count,
            "pending_referral_count": row.pending_referral_count,
            "latest_appointment_status": row.latest_appointment_status,
            "projection_updated_at": row.projection_updated_at,
        }
        if fields:
            record = {k: v for k, v in record.items() if k in fields}
        return ToolResult(
            tool="get_record", allowed=True, data=record, evidence_ids=[row.patient_id]
        )
    return _deny("get_record", f"Entity '{entity}' does not support get_record.")


def search_records(
    db: Session, entity: str, min_priority_score: int | None = None, limit: int = 5
) -> ToolResult:
    if entity not in ALLOWED_ENTITIES:
        return _deny(
            "search_records",
            f"Entity '{entity}' is not exposed by this gateway; agents do not query the "
            "production/source store directly.",
        )
    limit = max(1, min(limit, MAX_SEARCH_LIMIT))
    if entity == "care_work_queue":
        query = select(CareWorkQueue).order_by(CareWorkQueue.priority_score.desc())
        if min_priority_score is not None:
            query = query.where(CareWorkQueue.priority_score >= min_priority_score)
        rows = list(db.scalars(query.limit(limit)))
        data = [
            {
                "patient_id": row.patient_id,
                "patient_display_name": row.patient_display_name,
                "priority_score": row.priority_score,
            }
            for row in rows
        ]
        return ToolResult(
            tool="search_records",
            allowed=True,
            data=data,
            evidence_ids=[row.patient_id for row in rows],
        )
    return _deny("search_records", f"Entity '{entity}' does not support search_records.")


def get_change_history(db: Session, entity: str, record_id: str, limit: int = 10) -> ToolResult:
    if entity not in ALLOWED_ENTITIES:
        return _deny(
            "get_change_history",
            f"Entity '{entity}' is not exposed by this gateway; agents do not query the "
            "production/source store directly.",
        )
    limit = max(1, min(limit, MAX_SEARCH_LIMIT))
    rows = list(
        db.scalars(
            select(PatientTimeline)
            .where(PatientTimeline.patient_id == record_id)
            .order_by(PatientTimeline.occurred_at.desc())
            .limit(limit)
        )
    )
    data = [
        {
            "event_id": row.event_id,
            "event_type": row.event_type,
            "summary": row.summary,
            "occurred_at": row.occurred_at,
        }
        for row in rows
    ]
    return ToolResult(
        tool="get_change_history",
        allowed=True,
        data=data,
        evidence_ids=[row.event_id for row in rows],
    )


def get_freshness_status(
    db: Session, entity: str, record_id: str, budget_seconds: float = 300
) -> ToolResult:
    if entity not in ALLOWED_ENTITIES:
        return _deny(
            "get_freshness_status",
            f"Entity '{entity}' is not exposed by this gateway; agents do not query the "
            "production/source store directly.",
        )
    store = build_context_store(db, patient_ids=[record_id])
    entry = store.get(record_id)
    if not entry:
        return _deny("get_freshness_status", f"No context entry for id '{record_id}'.")
    result = evaluate_freshness(entry, budget_seconds=budget_seconds)
    return ToolResult(
        tool="get_freshness_status",
        allowed=True,
        data={
            "patient_id": result.patient_id,
            "source_record_id": result.source_record_id,
            "operation": result.operation,
            "source_commit_at": result.source_commit_at,
            "context_updated_at": result.context_updated_at,
            "retrieval_at": result.retrieval_at,
            "age_seconds": result.age_seconds,
            "context_age_seconds": result.context_age_seconds,
            "source_age_seconds": result.source_age_seconds,
            "source_to_context_lag_seconds": result.source_to_context_lag_seconds,
            "budget_seconds": result.budget_seconds,
            "decision": result.decision,
            "reason": result.reason,
        },
        evidence_ids=[record_id],
    )


def invoke_tool(db: Session, tool_name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
    """Single dispatch entry point used by both direct calls and the deterministic client."""
    arguments = arguments or {}
    if tool_name not in ALLOWED_TOOLS:
        return _deny(
            tool_name,
            f"Tool '{tool_name}' is not on the read-only allowlist; write-like or arbitrary "
            "operations are refused by this gateway.",
        )
    if tool_name == "list_entities":
        return list_entities()
    if tool_name == "get_record":
        return get_record(db, **arguments)
    if tool_name == "search_records":
        return search_records(db, **arguments)
    if tool_name == "get_change_history":
        return get_change_history(db, **arguments)
    if tool_name == "get_freshness_status":
        return get_freshness_status(db, **arguments)
    return _deny(tool_name, "Unhandled tool.")  # pragma: no cover - guarded by ALLOWED_TOOLS
