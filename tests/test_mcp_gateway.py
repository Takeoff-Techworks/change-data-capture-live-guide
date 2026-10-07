from app.db import SessionLocal
from app.main import bootstrap
from app.mcp import gateway
from app.mcp.agent import DeterministicMCPClient
from app.services.workflow_service import update_task


def test_list_entities_excludes_raw_source_tables():
    result = gateway.list_entities()
    assert result.allowed
    names = {item["entity"] for item in result.data}
    assert names == {"care_work_queue", "patient_timeline"}
    assert "patients" not in names


def test_get_record_bounded_lookup():
    bootstrap()
    db = SessionLocal()
    try:
        result = gateway.get_record(db, "care_work_queue", "p2")
        assert result.allowed
        assert result.data["patient_id"] == "p2"
        assert result.evidence_ids == ["p2"]
    finally:
        db.close()


def test_denies_disallowed_entity():
    bootstrap()
    db = SessionLocal()
    try:
        result = gateway.get_record(db, "patients", "p2")
        assert not result.allowed
        assert "not exposed" in result.denial_reason
        assert result.data is None
    finally:
        db.close()


def test_denies_unapproved_field():
    bootstrap()
    db = SessionLocal()
    try:
        result = gateway.get_record(db, "care_work_queue", "p2", fields=["birth_year"])
        assert not result.allowed
        assert "not approved" in result.denial_reason
    finally:
        db.close()


def test_denies_write_like_operation():
    bootstrap()
    db = SessionLocal()
    try:
        result = gateway.invoke_tool(db, "update_record", {"entity": "care_work_queue"})
        assert not result.allowed
        assert "read-only allowlist" in result.denial_reason
    finally:
        db.close()


def test_search_records_is_bounded_and_capped():
    bootstrap()
    db = SessionLocal()
    try:
        result = gateway.search_records(db, "care_work_queue", limit=1000)
        assert result.allowed
        assert len(result.data) <= gateway.MAX_SEARCH_LIMIT
    finally:
        db.close()


def test_change_history_reflects_cdc_events():
    bootstrap()
    db = SessionLocal()
    try:
        before = gateway.get_change_history(db, "care_work_queue", "p2")
        update_task(db, "task1", status="in_progress")
        after = gateway.get_change_history(db, "care_work_queue", "p2")
        assert len(after.data) >= len(before.data)
        assert after.evidence_ids
    finally:
        db.close()


def test_deterministic_client_logs_calls_with_evidence_and_freshness():
    bootstrap()
    db = SessionLocal()
    try:
        client = DeterministicMCPClient()
        client.ask(db, "Is this current?", patient_id="p2")
        assert len(client.call_log) == 1
        entry = client.call_log[0]
        assert entry.tool == "get_freshness_status"
        assert entry.allowed
        assert entry.freshness is not None
        assert entry.freshness["decision"] in {"allow", "block"}
    finally:
        db.close()


def test_freshness_status_exposes_distinguishable_measures():
    bootstrap()
    db = SessionLocal()
    try:
        result = gateway.get_freshness_status(db, "care_work_queue", "p2", budget_seconds=10_000)
        assert result.allowed
        data = result.data
        assert "context_age_seconds" in data
        assert "source_age_seconds" in data
        assert "source_to_context_lag_seconds" in data
        assert data["source_age_seconds"] >= data["context_age_seconds"]
    finally:
        db.close()


def test_get_record_denies_raw_source_entity():
    bootstrap()
    db = SessionLocal()
    try:
        result = gateway.get_record(db, "patients", "p2")
        assert not result.allowed
        assert result.evidence_ids == []
    finally:
        db.close()
