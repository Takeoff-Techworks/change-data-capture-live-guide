"""Receive Debezium HTTP events, or forward a selected lab update to Northstar."""

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import Request, urlopen


def decode_event(body: bytes) -> dict:
    event = json.loads(body)
    if isinstance(event, dict) and "payload" in event:
        event = event["payload"]
    if not isinstance(event, dict) or event.get("op") not in {"r", "c", "u", "d"}:
        raise ValueError("Expected one Debezium row-change envelope")
    if not isinstance(event.get("source"), dict):
        raise ValueError("Missing source metadata")  # noqa: TRY004 - invalid JSON input
    if not isinstance(event.get("after") or event.get("before"), dict):
        raise ValueError("Missing row image")  # noqa: TRY004 - invalid JSON input
    return event


def record_event(event: dict, journal: Path) -> None:
    # Acknowledge only after the journal write is flushed to storage.
    with journal.open("a", encoding="utf-8") as output:
        output.write(json.dumps(event) + "\n")
        output.flush()
        os.fsync(output.fileno())


def handler_for(journal: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/health":
                self.send_error(404)
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ready\n")

        def do_POST(self):
            if self.path != "/events":
                self.send_error(404)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1_048_576:
                    raise ValueError("Expected a body between 1 byte and 1 MiB")
                event = decode_event(self.rfile.read(size))
            except (ValueError, UnicodeError) as exc:
                self.send_error(400, str(exc))
                return
            try:
                record_event(event, journal)
            except OSError:
                self.send_error(503, "Journal write failed; retry delivery")
                return
            self.send_response(204)
            self.end_headers()
            print(json.dumps(event), flush=True)

    return Handler


def select_update(lines, database: str, appointment_id: str, reason: str) -> dict:
    selected = None
    for line in lines:
        if not line.strip():
            continue
        event = decode_event(line.encode())
        source = event["source"]
        after = event.get("after") or {}
        if (
            event["op"] == "u"
            and source.get("db") == database
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
    # The current app normalizer reads envelope ts_ms as source commit time.
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
    serve = commands.add_parser("serve", help="Journal HTTP events for the lab")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8081)
    serve.add_argument("--journal", type=Path, default=Path("/data/events.jsonl"))
    forward = commands.add_parser("forward", help="Read JSONL from stdin and post one update")
    forward.add_argument("--database", required=True)
    forward.add_argument("--appointment-id", required=True)
    forward.add_argument("--reason", required=True)
    forward.add_argument("--app-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if args.command == "serve":
        args.journal.parent.mkdir(parents=True, exist_ok=True)
        args.journal.touch(exist_ok=True)
        with HTTPServer((args.host, args.port), handler_for(args.journal)) as server:
            print(f"Listening on {args.host}:{args.port}; journal: {args.journal}", flush=True)
            server.serve_forever()
    else:
        try:
            event = select_update(sys.stdin, args.database, args.appointment_id, args.reason)
        except ValueError as exc:
            parser.error(str(exc))
        result = forward_event(event, args.app_url)
        print("Ingested canonical event:", result["event_id"])
        print("Source:", result["source"], "capture method:", result["capture_method"])


if __name__ == "__main__":
    main()
