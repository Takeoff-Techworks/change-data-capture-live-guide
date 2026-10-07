"""Run the PostgreSQL app bonus and forward its captured update."""

import argparse
import json
import os
import sys
from urllib.request import Request, urlopen


DATABASE_URLS = {
    "postgres": (
        "postgresql+psycopg://northstar_app:northstar-app-lab-only"
        "@127.0.0.1:15432/northstar_app"
    ),
    "sqlite": "sqlite:///./northstar.db",
}


def configure(database: str) -> None:
    os.environ.update(
        {
            "APP_DATABASE_URL": DATABASE_URLS[database],
            "CDC_MODE": "simulated",
            "CDC_AUTO_PROCESS": "true",
            "CDC_CONSUMER_PAUSED": "false",
            "CDC_FAILURE_MODE": "none",
        }
    )


def decode_event(line: str) -> dict:
    event = json.loads(line)
    if isinstance(event, dict) and "payload" in event:
        event = event["payload"]
    if not isinstance(event, dict) or event.get("op") not in {"r", "c", "u", "d"}:
        raise ValueError("Expected one Debezium row-change envelope")
    return event


def select_update(lines, appointment_id: str, reason: str) -> dict:
    selected = None
    for line in lines:
        if not line.strip():
            continue
        event = decode_event(line)
        source = event.get("source") or {}
        after = event.get("after") or {}
        if (
            event["op"] == "u"
            and source.get("db") == "northstar_app"
            and source.get("schema") == "public"
            and source.get("table") == "appointments"
            and after.get("appointment_id") == appointment_id
            and after.get("reason_code") == reason
        ):
            selected = event
    if selected is None:
        raise ValueError("Matching captured update not found; wait for capture and check filters")
    return selected


def forward_event(event: dict, app_url: str) -> dict:
    envelope = dict(event)
    envelope["key"] = {"appointment_id": event["after"]["appointment_id"]}
    if event["source"].get("ts_ms") is not None:
        envelope["ts_ms"] = event["source"]["ts_ms"]
    request = Request(
        app_url.rstrip("/") + "/api/ingest/debezium?persona=admin",
        data=json.dumps({"payload": envelope}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify")
    commands.add_parser("seed")
    serve = commands.add_parser("serve")
    serve.add_argument("database", choices=DATABASE_URLS)
    forward = commands.add_parser("forward")
    forward.add_argument("--appointment-id", required=True)
    forward.add_argument("--reason", required=True)
    forward.add_argument("--app-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    if args.command in {"verify", "seed"}:
        configure("postgres")
    if args.command == "verify":
        from sqlalchemy import text

        from app.db import engine

        with engine.connect() as connection:
            print(connection.execute(text("SELECT current_database(), current_user")).one())
    elif args.command == "seed":
        from app.main import bootstrap

        bootstrap()
        print("Synthetic demo seeded.")
    elif args.command == "serve":
        configure(args.database)
        import uvicorn

        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
    else:
        try:
            event = select_update(sys.stdin, args.appointment_id, args.reason)
        except ValueError as exc:
            parser.error(str(exc))
        result = forward_event(event, args.app_url)
        print("Ingested canonical event:", result["event_id"])
        print("Source:", result["source"], "capture method:", result["capture_method"])


if __name__ == "__main__":
    main()
