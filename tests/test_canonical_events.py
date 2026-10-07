import json
from pathlib import Path

from app.cdc.normalizer import debezium_event, sqlserver_event

FIXTURES = Path(__file__).parent / "fixtures"


def payload(name):
    return json.loads((FIXTURES / name).read_text())


def test_sqlserver_update_normalizes():
    event = sqlserver_event(payload("sqlserver_appointments_update.json"))
    assert event.operation == "u" and event.patient_id == "p2" and event.table == "appointments"


def test_debezium_maps_key_and_before_after():
    event = debezium_event(payload("debezium_postgres_appointments_update.json"))
    assert event.entity_key["appointment_id"] == "appt2" and event.before["status"] == "scheduled"
