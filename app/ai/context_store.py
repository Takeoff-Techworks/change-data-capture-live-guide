"""A tiny, deterministic agent-context (retrieval) store.

This is intentionally not a vector database. It builds one small, human-readable
"context entry" per patient from the same authorized projection facts the
assistant already uses (see `app.services.policy_service`), plus freshness
metadata sourced from the CDC pipeline (`CanonicalEvent`, `CareWorkQueue`).

Session 4 teaches that agent-context correctness depends on freshness and
pipeline observability, not just model quality. Every entry records what it
was built from (source record id, operation, source commit time) and when it
was assembled, so a caller can compute how stale it is at retrieval time and
apply a freshness-budget policy before treating an answer as authoritative.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CanonicalEvent, CareWorkQueue


def utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


@dataclass
class ContextEntry:
    """One retrieval-ready record for a single patient's coordination status."""

    patient_id: str
    evidence: str
    facts: dict[str, Any]
    source_record_id: str | None
    source_table: str | None
    operation: str | None
    source_commit_at: datetime | None
    context_updated_at: datetime


@dataclass
class ContextStore:
    """An in-memory collection of context entries keyed by patient_id."""

    entries: dict[str, ContextEntry] = field(default_factory=dict)

    def get(self, patient_id: str) -> ContextEntry | None:
        return self.entries.get(patient_id)


def _latest_event_for_patient(db: Session, patient_id: str) -> CanonicalEvent | None:
    return db.scalar(
        select(CanonicalEvent)
        .where(CanonicalEvent.patient_id == patient_id, CanonicalEvent.status == "processed")
        .order_by(CanonicalEvent.captured_at.desc())
    )


def _entity_key(event: CanonicalEvent | None) -> str | None:
    if not event:
        return None
    try:
        key = json.loads(event.entity_key_json)
    except (TypeError, ValueError):
        return None
    if not key:
        return None
    return next(iter(key.values()), None)


def _build_entry(db: Session, row: CareWorkQueue, built_at: datetime) -> ContextEntry:
    reasons = json.loads(row.priority_reasons_json)
    facts = {
        "patient_id": row.patient_id,
        "patient_display_name": row.patient_display_name,
        "priority_score": row.priority_score,
        "priority_reasons": reasons,
        "open_task_count": row.open_task_count,
        "overdue_task_count": row.overdue_task_count,
        "pending_referral_count": row.pending_referral_count,
        "latest_appointment_status": row.latest_appointment_status,
    }
    evidence = (
        f"{row.patient_display_name} (patient_id={row.patient_id}) has priority score "
        f"{row.priority_score}: {'; '.join(reasons) or 'no active priority rules'}. "
        f"Open tasks: {row.open_task_count} (overdue {row.overdue_task_count}). "
        f"Pending referrals: {row.pending_referral_count}."
    )
    event = _latest_event_for_patient(db, row.patient_id)
    return ContextEntry(
        patient_id=row.patient_id,
        evidence=evidence,
        facts=facts,
        source_record_id=_entity_key(event) or row.patient_id,
        source_table=event.source_table if event else None,
        operation=event.operation if event else None,
        source_commit_at=_aware(event.source_commit_at)
        if event
        else _aware(row.last_source_commit_at),
        context_updated_at=built_at,
    )


def build_context_store(db: Session, patient_ids: list[str] | None = None) -> ContextStore:
    """Build a small agent-context/retrieval representation from seed data.

    Reuses the existing, authorized `CareWorkQueue` projection (the same facts
    the deterministic assistant is allowed to see) rather than inventing a
    parallel domain or a vector database.
    """
    built_at = utcnow()
    query = select(CareWorkQueue)
    if patient_ids:
        query = query.where(CareWorkQueue.patient_id.in_(patient_ids))
    rows = list(db.scalars(query))
    store = ContextStore()
    for row in rows:
        store.entries[row.patient_id] = _build_entry(db, row, built_at)
    return store


def refresh_entry(db: Session, store: ContextStore, patient_id: str) -> ContextEntry | None:
    """Refresh only the affected context entry after a CDC event lands.

    This is the crux of the Session 4 lesson: instead of rebuilding the whole
    context/index, only the entries touched by a change are refreshed.
    """
    row = db.get(CareWorkQueue, patient_id)
    if not row:
        store.entries.pop(patient_id, None)
        return None
    entry = _build_entry(db, row, utcnow())
    store.entries[patient_id] = entry
    return entry


@dataclass
class FreshnessResult:
    patient_id: str
    source_record_id: str | None
    operation: str | None
    source_commit_at: datetime | None
    context_updated_at: datetime
    retrieval_at: datetime
    age_seconds: float
    budget_seconds: float
    decision: str
    reason: str
    context_age_seconds: float = 0.0
    source_age_seconds: float | None = None
    source_to_context_lag_seconds: float | None = None


def evaluate_freshness(
    entry: ContextEntry, budget_seconds: float, retrieval_at: datetime | None = None
) -> FreshnessResult:
    """Apply a configurable freshness budget to a context entry.

    Three distinguishable measures are computed whenever the underlying
    source commit time is known:

    * `source_age_seconds` -- how long it has been since the *source* row was
      committed (retrieval time minus source commit time). This is "how old
      is the fact in the real world".
    * `source_to_context_lag_seconds` -- how long the CDC/projection pipeline
      took to reflect that source commit in this context entry (context
      update time minus source commit time). This is "how far behind is the
      pipeline".
    * `context_age_seconds` -- how long it has been since this context entry
      was last built/refreshed (retrieval time minus context update time).
      This is "how stale could my in-memory copy be, even if the pipeline is
      instant".

    `age_seconds` is kept as a backwards-compatible alias of
    `context_age_seconds`, since that is the measure the freshness *budget*
    policy below is enforced against: it is the one thing a caller can act on
    by refreshing the context entry, independent of source or pipeline
    behavior.
    """
    retrieval_at = retrieval_at or utcnow()
    context_age_seconds = max(0.0, (retrieval_at - entry.context_updated_at).total_seconds())
    source_age_seconds: float | None = None
    source_to_context_lag_seconds: float | None = None
    if entry.source_commit_at is not None:
        source_age_seconds = max(0.0, (retrieval_at - entry.source_commit_at).total_seconds())
        source_to_context_lag_seconds = max(
            0.0, (entry.context_updated_at - entry.source_commit_at).total_seconds()
        )
    if context_age_seconds > budget_seconds:
        decision, reason = (
            "block",
            f"Context age {context_age_seconds:.1f}s exceeds freshness budget {budget_seconds:.1f}s",
        )
    else:
        decision, reason = (
            "allow",
            f"Context age {context_age_seconds:.1f}s is within freshness budget {budget_seconds:.1f}s",
        )
    return FreshnessResult(
        patient_id=entry.patient_id,
        source_record_id=entry.source_record_id,
        operation=entry.operation,
        source_commit_at=entry.source_commit_at,
        context_updated_at=entry.context_updated_at,
        retrieval_at=retrieval_at,
        age_seconds=context_age_seconds,
        budget_seconds=budget_seconds,
        decision=decision,
        reason=reason,
        context_age_seconds=context_age_seconds,
        source_age_seconds=source_age_seconds,
        source_to_context_lag_seconds=source_to_context_lag_seconds,
    )


@dataclass
class RetrievalAnswer:
    """A minimal deterministic retrieval-and-answer result.

    Unlike a bare `ContextStore.get(...)` lookup, this always returns the
    evidence record id(s) that back the answer and applies the freshness
    budget policy before treating the answer as authoritative -- the same
    two things a real retrieval-augmented-generation path must get right.
    """

    patient_id: str
    question: str
    answer: str
    evidence_ids: list[str]
    freshness: FreshnessResult
    authoritative: bool


def retrieve_and_answer(
    db: Session,
    store: ContextStore,
    patient_id: str,
    question: str,
    budget_seconds: float = 300,
    retrieval_at: datetime | None = None,
) -> RetrievalAnswer:
    """Retrieve the bounded context entry for `patient_id` and answer `question`.

    This is intentionally tiny: it looks up (or, if missing, builds) the one
    context entry for the patient, applies `evaluate_freshness`, and returns
    an evidence-carrying answer. When the freshness budget is exceeded the
    answer is withheld (`authoritative=False`) instead of silently returning
    a stale fact.
    """
    entry = store.get(patient_id)
    if entry is None:
        entry = refresh_entry(db, store, patient_id)
    if entry is None:
        freshness = FreshnessResult(
            patient_id=patient_id,
            source_record_id=None,
            operation=None,
            source_commit_at=None,
            context_updated_at=retrieval_at or utcnow(),
            retrieval_at=retrieval_at or utcnow(),
            age_seconds=0.0,
            budget_seconds=budget_seconds,
            decision="block",
            reason="No context entry exists for this patient.",
            context_age_seconds=0.0,
        )
        return RetrievalAnswer(
            patient_id=patient_id,
            question=question,
            answer="No context available for that patient.",
            evidence_ids=[],
            freshness=freshness,
            authoritative=False,
        )
    freshness = evaluate_freshness(entry, budget_seconds=budget_seconds, retrieval_at=retrieval_at)
    evidence_ids = [entry.source_record_id or entry.patient_id]
    if freshness.decision == "block":
        answer = (
            f"Answer withheld pending refresh: {freshness.reason}. "
            f"Last known evidence: {entry.evidence}"
        )
        authoritative = False
    else:
        answer = entry.evidence
        authoritative = True
    return RetrievalAnswer(
        patient_id=patient_id,
        question=question,
        answer=answer,
        evidence_ids=evidence_ids,
        freshness=freshness,
        authoritative=authoritative,
    )
