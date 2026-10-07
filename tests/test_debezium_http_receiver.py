import importlib.util
import io
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.cdc.normalizer import debezium_event

# Load the standalone Docker helper without making the lab directories packages.
receiver_path = (
    Path(__file__).resolve().parents[1]
    / "docker/postgres-app-integration/receiver/debezium_http_receiver.py"
)
spec = importlib.util.spec_from_file_location("debezium_http_receiver", receiver_path)
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)

bridge_path = (
    Path(__file__).resolve().parents[1]
    / "exercises/03-postgres/postgres_cdc_bridge.py"
)
bridge_spec = importlib.util.spec_from_file_location("postgres_cdc_bridge", bridge_path)
bridge = importlib.util.module_from_spec(bridge_spec)
bridge_spec.loader.exec_module(bridge)


def change(database="northstar_app", reason="postgres-live-lab"):
    return {
        "op": "u",
        "source": {
            "db": database,
            "schema": "public",
            "table": "appointments",
            "lsn": 123,
            "ts_ms": 1700000000000,
        },
        "before": {"appointment_id": "appt3", "patient_id": "p3", "status": "scheduled"},
        "after": {
            "appointment_id": "appt3",
            "patient_id": "p3",
            "status": "no_show",
            "reason_code": reason,
        },
        "ts_ms": 1700000001000,
        "transaction": None,
    }


@pytest.mark.parametrize("wrapped", [False, True])
def test_receiver_accepts_plain_and_schema_wrapped_event(wrapped):
    event = change()
    body = {"schema": {}, "payload": event} if wrapped else event
    assert receiver.decode_event(json.dumps(body).encode()) == event


@pytest.mark.parametrize("body", [b"null", b"[]", b"{}", b"not json"])
def test_receiver_rejects_non_events(body):
    with pytest.raises(ValueError):
        receiver.decode_event(body)


def test_receiver_acknowledges_after_durable_write(tmp_path, monkeypatch):
    journal = tmp_path / "events.jsonl"
    body = json.dumps(change()).encode()
    handler_type = receiver.handler_for(journal)
    handler = handler_type.__new__(handler_type)
    handler.path = "/events"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = io.BytesIO(body)
    handler.end_headers = Mock()
    handler.send_error = Mock()
    actions = []
    monkeypatch.setattr(receiver.os, "fsync", lambda fd: actions.append("fsync"))
    handler.send_response = lambda code: actions.append(code)
    handler.do_POST()
    assert actions == ["fsync", 204]
    assert json.loads(journal.read_text()) == change()
    handler.send_error.assert_not_called()


def test_receiver_does_not_acknowledge_failed_journal_write(tmp_path, monkeypatch):
    handler_type = receiver.handler_for(tmp_path / "events.jsonl")
    handler = handler_type.__new__(handler_type)
    body = json.dumps(change()).encode()
    handler.path = "/events"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = io.BytesIO(body)
    handler.send_error = Mock()
    handler.send_response = Mock()
    monkeypatch.setattr(receiver, "record_event", Mock(side_effect=OSError("disk full")))
    handler.do_POST()
    handler.send_error.assert_called_once_with(503, "Journal write failed; retry delivery")
    handler.send_response.assert_not_called()


def test_select_update_filters_database_and_marker_and_uses_last_match():
    first = change()
    last = change()
    last["source"]["lsn"] = 456
    events = [first, change("northstar_cdc_lab"), last, change(reason="unrelated")]
    selected = receiver.select_update(
        [json.dumps(e) for e in events], "northstar_app", "appt3", "postgres-live-lab"
    )
    assert selected == last
    with pytest.raises(ValueError, match="not found"):
        receiver.select_update([json.dumps(first)], "other_db", "appt3", "postgres-live-lab")


def test_forwarded_event_normalizes_with_null_transaction(monkeypatch):
    requests = []

    def capture(request, timeout):
        requests.append(request)
        return io.BytesIO(b'{"event_id":"example"}')

    monkeypatch.setattr(receiver, "urlopen", capture)
    original = change()
    assert receiver.forward_event(original, "http://localhost:8000/") == {"event_id": "example"}
    request = requests[0]
    assert request.full_url == "http://localhost:8000/api/ingest/debezium?persona=admin"
    event = debezium_event(json.loads(request.data)["payload"])
    assert event.entity_key == {"appointment_id": "appt3"}
    assert event.patient_id == "p3" and event.operation == "u"
    assert event.correlation_id is None
    assert int(event.source_commit_at.timestamp() * 1000) == original["source"]["ts_ms"]
    assert original["ts_ms"] == 1700000001000


def test_postgres_bridge_selects_the_last_matching_app_update():
    first = change()
    last = change()
    last["source"]["lsn"] = 456
    events = [first, change("northstar_cdc_lab"), last, change(reason="unrelated")]
    selected = bridge.select_update(
        [json.dumps(event) for event in events], "appt3", "postgres-live-lab"
    )
    assert selected == last


def test_postgres_bridge_forwards_a_normalizable_event(monkeypatch):
    monkeypatch.setattr(
        bridge,
        "urlopen",
        lambda request, timeout: io.BytesIO(b'{"event_id":"bridge-example"}'),
    )
    original = change()
    assert bridge.forward_event(original, "http://localhost:8000/") == {
        "event_id": "bridge-example"
    }
