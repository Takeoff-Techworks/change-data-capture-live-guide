import re
from pathlib import Path

from sqlalchemy import String, UniqueConstraint, create_engine, select
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db import Base
from app.models import (
    Appointment,
    CanonicalEvent,
    CareTask,
    CareTeamAssignment,
    Patient,
    Provider,
    Referral,
    User,
)
from app.seed import seed_demo
from app.services.workflow_service import update_appointment

ROOT = Path(__file__).resolve().parents[1]


def test_sqlserver_index_keys_have_bounded_string_types():
    dialect = mssql.dialect()
    for table in Base.metadata.sorted_tables:
        assert str(CreateTable(table).compile(dialect=dialect))
        keys = list(table.primary_key.columns)
        for constraint in table.constraints:
            if isinstance(constraint, UniqueConstraint):
                keys.extend(constraint.columns)
        for index in table.indexes:
            keys.extend(index.columns)
        for column in keys:
            if isinstance(column.type, String):
                assert column.type.length is not None, f"Unbounded index key: {column}"


def test_sqlserver_nullable_raw_event_key_uses_filtered_unique_index():
    table = CanonicalEvent.__table__
    index = next(i for i in table.indexes if list(i.columns.keys()) == ["raw_event_id"])
    ddl = str(CreateIndex(index).compile(dialect=mssql.dialect()))
    assert "UNIQUE INDEX" in ddl
    assert "WHERE raw_event_id IS NOT NULL" in ddl
    assert not any(
        isinstance(c, UniqueConstraint) and "raw_event_id" in c.columns
        for c in table.constraints
    )


def test_seed_and_workflow_with_foreign_keys_enforced():
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            seed_demo(db)
            seed_demo(db)
            assert len(list(db.scalars(select(Patient)))) == 10
            assert len(list(db.scalars(select(Appointment)))) == 10
            update_appointment(db, "appt3", status="completed")
            assert db.get(Appointment, "appt3").status == "completed"
            assert db.scalar(select(CanonicalEvent)).status == "processed"
    finally:
        engine.dispose()


def test_source_database_init_scripts_match_sqlite_seed_ids():
    expected = _sqlite_seed_ids()
    sqlserver_init = ROOT / "docker" / "database-capture" / "sqlserver" / "init.sql"
    postgres_init = ROOT / "docker" / "postgres-app-integration" / "postgres" / "init.sql"

    for script in (sqlserver_init, postgres_init):
        actual = _seed_ids_from_sql(script.read_text())
        assert actual == expected, f"{script} seed rows drifted from app.seed.seed_demo"


def test_exercises_reference_seeded_appointment_states():
    expected = _sqlite_seed_appointment_statuses()
    documents = {
        "sqlserver_readme": ROOT / "exercises" / "02-sqlserver" / "README.md",
        "sqlserver_bonus": ROOT / "exercises" / "02-sqlserver" / "BONUS.md",
        "postgres_readme": ROOT / "exercises" / "03-postgres" / "README.md",
    }

    assert expected["appt1"] == "completed"
    assert expected["appt2"] == "no_show"
    assert expected["appt3"] == "scheduled"
    assert expected["appt4"] == "canceled"

    postgres_text = documents["postgres_readme"].read_text()
    assert "appt1` | `u` | `completed` before, `no_show` after" in postgres_text
    assert "WHERE appointment_id = 'appt1'" in postgres_text
    assert "WHERE appointment_id = 'lab-appt'" in postgres_text

    for key in ("sqlserver_bonus", "postgres_readme"):
        text = documents[key].read_text()
        assert "appt3" in text
        assert "starts as `scheduled`" in text or "status = 'scheduled'" in text

    sqlserver_text = documents["sqlserver_readme"].read_text()
    assert "appt2`'s current reason code" in sqlserver_text
    assert "Expected the seeded appt2 row" in sqlserver_text


def _sqlite_seed_ids() -> dict[str, set[str]]:
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            seed_demo(db)
            return {
                "users": set(db.scalars(select(User.user_id))),
                "providers": set(db.scalars(select(Provider.provider_id))),
                "patients": set(db.scalars(select(Patient.patient_id))),
                "care_team_assignments": set(
                    db.scalars(select(CareTeamAssignment.assignment_id))
                ),
                "appointments": set(db.scalars(select(Appointment.appointment_id))),
                "referrals": set(db.scalars(select(Referral.referral_id))),
                "care_tasks": set(db.scalars(select(CareTask.task_id))),
            }
    finally:
        engine.dispose()


def _sqlite_seed_appointment_statuses() -> dict[str, str]:
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            seed_demo(db)
            return dict(db.execute(select(Appointment.appointment_id, Appointment.status)).all())
    finally:
        engine.dispose()


def _seed_ids_from_sql(sql: str) -> dict[str, set[str]]:
    return {
        table: set(re.findall(pattern, sql))
        for table, pattern in {
            "users": r"\(?N?'([^']+)'\s*,\s*N?'(?:admin|receptionist|nurse|doctor|pa)'",
            "providers": r"\(?N?'(prov-[^']+)'",
            "patients": r"\(?N?'(p\d+)'\s*,\s*N?'[A-Z][^']+'\s*,\s*19\d\d",
            "care_team_assignments": r"\(?N?'(a\d+)'\s*,\s*N?'p\d+'",
            "appointments": r"\(?N?'(appt\d+)'\s*,\s*N?'p\d+'",
            "referrals": r"\(?N?'(ref\d+)'\s*,\s*N?'p\d+'",
            "care_tasks": r"\(?N?'(task\d+)'\s*,\s*N?'p\d+'",
        }.items()
    }
