from datetime import timedelta

from app.ai.context_store import (
    build_context_store,
    evaluate_freshness,
    refresh_entry,
    retrieve_and_answer,
)
from app.db import SessionLocal
from app.main import bootstrap
from app.services.workflow_service import update_task


def test_context_entry_records_freshness_metadata():
    bootstrap()
    db = SessionLocal()
    try:
        store = build_context_store(db, patient_ids=["p2"])
        entry = store.get("p2")
        assert entry is not None
        assert entry.patient_id == "p2"
        assert entry.context_updated_at is not None
        assert entry.evidence
    finally:
        db.close()


def test_freshness_policy_blocks_when_budget_exceeded():
    bootstrap()
    db = SessionLocal()
    try:
        store = build_context_store(db, patient_ids=["p2"])
        entry = store.get("p2")
        result = evaluate_freshness(entry, budget_seconds=0)
        assert result.decision == "block"
        assert result.age_seconds >= 0

        fresh_result = evaluate_freshness(entry, budget_seconds=10_000)
        assert fresh_result.decision == "allow"
    finally:
        db.close()


def test_refresh_entry_updates_only_the_affected_patient():
    bootstrap()
    db = SessionLocal()
    try:
        store = build_context_store(db, patient_ids=["p2", "p3"])
        original_p3 = store.get("p3")
        original_p2_updated_at = store.get("p2").context_updated_at

        update_task(db, "task1", status="in_progress")

        refreshed = refresh_entry(db, store, "p2")
        assert refreshed is not None
        assert refreshed.context_updated_at >= original_p2_updated_at
        # The unaffected entry is untouched by the targeted refresh.
        assert store.get("p3") is original_p3
    finally:
        db.close()


def test_freshness_distinguishes_source_age_lag_and_context_age():
    bootstrap()
    db = SessionLocal()
    try:
        store = build_context_store(db, patient_ids=["p2"])
        entry = store.get("p2")
        assert entry.source_commit_at is not None

        # Simulate a moment shortly after the context was built.
        retrieval_at = entry.context_updated_at + timedelta(seconds=30)
        result = evaluate_freshness(entry, budget_seconds=10_000, retrieval_at=retrieval_at)

        assert abs(result.context_age_seconds - 30) < 1.0
        assert result.age_seconds == result.context_age_seconds  # backwards-compatible alias
        assert result.source_age_seconds is not None
        assert result.source_to_context_lag_seconds is not None
        # Source age is at least as large as the source-to-context lag, since
        # the source commit necessarily happens before (or at) the context
        # update that captured it.
        assert result.source_age_seconds >= result.source_to_context_lag_seconds
        # And source age should be strictly larger than context age alone,
        # since it also includes the pipeline lag.
        assert result.source_age_seconds >= result.context_age_seconds
    finally:
        db.close()


def test_retrieve_and_answer_returns_evidence_ids_and_allows_when_fresh():
    bootstrap()
    db = SessionLocal()
    try:
        store = build_context_store(db, patient_ids=["p2"])
        result = retrieve_and_answer(
            db, store, "p2", "What is the current priority?", budget_seconds=10_000
        )
        assert result.authoritative
        assert result.evidence_ids
        assert result.freshness.decision == "allow"
        assert result.answer
    finally:
        db.close()


def test_retrieve_and_answer_blocks_authoritative_answer_when_budget_exceeded():
    bootstrap()
    db = SessionLocal()
    try:
        store = build_context_store(db, patient_ids=["p2"])
        result = retrieve_and_answer(
            db, store, "p2", "What is the current priority?", budget_seconds=0
        )
        assert not result.authoritative
        assert result.freshness.decision == "block"
        # Evidence ids are still surfaced even when the answer is withheld,
        # so a caller can show what would be refreshed.
        assert result.evidence_ids
    finally:
        db.close()


def test_retrieve_and_answer_builds_missing_entry_on_demand():
    bootstrap()
    db = SessionLocal()
    try:
        store = build_context_store(db, patient_ids=["p2"])  # p3 intentionally excluded
        assert store.get("p3") is None
        result = retrieve_and_answer(db, store, "p3", "current status", budget_seconds=10_000)
        assert result.evidence_ids
        assert store.get("p3") is not None
    finally:
        db.close()
