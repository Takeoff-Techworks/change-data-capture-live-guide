from datetime import UTC, datetime
from uuid import uuid4

from app.schemas import CanonicalChangeEvent


def now() -> datetime:
    return datetime.now(UTC)


def _patient_id(before: dict | None, after: dict | None) -> str | None:
    return (after or before or {}).get("patient_id")


def simulated_event(
    table: str,
    operation: str,
    before: dict | None,
    after: dict | None,
    correlation_id: str | None = None,
) -> CanonicalChangeEvent:
    row = after or before or {}
    key_name = next((k for k in row if k.endswith("_id") and k != "patient_id"), "id")
    return CanonicalChangeEvent(
        event_id=str(uuid4()),
        source="simulated",
        capture_method="simulated",
        table=table,
        operation=operation,
        entity_key={key_name: str(row.get(key_name, "unknown"))},
        before=before,
        after=after,
        patient_id=_patient_id(before, after),
        source_commit_at=now(),
        captured_at=now(),
        correlation_id=correlation_id,
    )


def sqlserver_event(payload: dict) -> CanonicalChangeEvent:
    op = {1: "d", 2: "c", 3: "u", 4: "u", "delete": "d", "insert": "c", "update": "u"}.get(
        payload.get("__$operation") or payload.get("operation")
    )
    if not op:
        raise ValueError("SQL Server CDC payload requires a recognized __$operation")
    after = payload.get("after") or payload.get("row")
    before = payload.get("before")
    table = payload.get("table") or payload.get("source_table")
    if not table or not (after or before):
        raise ValueError("SQL Server CDC payload requires table and before/after row data")
    row = after or before
    key = payload.get("key") or {
        next((k for k in row if k.endswith("_id")), "id"): str(
            next((v for k, v in row.items() if k.endswith("_id")), "unknown")
        )
    }
    return CanonicalChangeEvent(
        event_id=str(uuid4()),
        source="sqlserver",
        capture_method="sqlserver_cdc",
        table=table,
        operation=op,
        entity_key={k: str(v) for k, v in key.items()},
        before=before,
        after=after,
        patient_id=_patient_id(before, after),
        source_commit_at=now(),
        captured_at=now(),
        correlation_id=payload.get("correlation_id"),
    )


def debezium_event(payload: dict) -> CanonicalChangeEvent:
    envelope = payload.get("payload", payload)
    op = envelope.get("op")
    if op == "r":
        op = "c"
    if op not in {"c", "u", "d"}:
        raise ValueError("Debezium payload requires op c, u, d, or r")
    source = envelope.get("source", {})
    table = envelope.get("table") or source.get("table")
    before, after = envelope.get("before"), envelope.get("after")
    if not table or not (before or after):
        raise ValueError("Debezium payload requires source.table and before/after")
    ts_ms = envelope.get("ts_ms")
    commit_at = datetime.fromtimestamp(ts_ms / 1000, UTC) if ts_ms else now()
    key_payload = payload.get("key", {})
    if isinstance(key_payload, dict) and "payload" in key_payload:
        key_payload = key_payload["payload"]
    row = after or before
    key = key_payload or {
        next((k for k in row if k.endswith("_id")), "id"): str(
            next((v for k, v in row.items() if k.endswith("_id")), "unknown")
        )
    }
    return CanonicalChangeEvent(
        event_id=str(uuid4()),
        source="postgres",
        capture_method="debezium_postgres",
        table=table,
        operation=op,
        entity_key={k: str(v) for k, v in key.items()},
        before=before,
        after=after,
        patient_id=_patient_id(before, after),
        source_commit_at=commit_at,
        captured_at=now(),
        correlation_id=(envelope.get("transaction") or {}).get("id"),
    )
