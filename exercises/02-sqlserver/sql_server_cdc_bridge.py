"""Forward the SQL Server lab update to the running Northstar app once.

Run from the repository root after exporting APP_DATABASE_URL as described
in this directory's BONUS.md, step 3.
"""

import json
import time
from urllib.request import Request, urlopen

from sqlalchemy import text

from app.db import engine


def main() -> None:
    assert engine.dialect.name == "mssql", "Select SQL Server before running this bridge"
    fields = (
        "appointment_id",
        "patient_id",
        "provider_id",
        "scheduled_start_at",
        "status",
        "reason_code",
        "updated_at",
    )
    deadline = time.monotonic() + 60
    before = after = None
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT DB_NAME()")) == "NorthstarApp"
        while time.monotonic() < deadline:
            low, high = connection.execute(
                text("""
                SELECT sys.fn_cdc_get_min_lsn('app_appointments'),
                       sys.fn_cdc_get_max_lsn()
            """)
            ).one()
            if low and high and low != bytes(10) and low <= high:
                rows = (
                    connection.execute(
                        text("""
                    SELECT * FROM cdc.fn_cdc_get_all_changes_app_appointments
                        (:low, :high, 'all update old')
                    WHERE appointment_id = 'appt3'
                    ORDER BY __$start_lsn, __$seqval, __$operation
                """),
                        {"low": low, "high": high},
                    )
                    .mappings()
                    .all()
                )
                after = next(
                    (
                        r
                        for r in reversed(rows)
                        if r["__$operation"] == 4
                        and r["status"] == "no_show"
                        and r["reason_code"] == "sqlserver-live-lab"
                    ),
                    None,
                )
                if after is not None:
                    before = next(
                        (
                            r
                            for r in rows
                            if r["__$operation"] == 3
                            and r["__$start_lsn"] == after["__$start_lsn"]
                            and r["__$seqval"] == after["__$seqval"]
                        ),
                        None,
                    )
                    if before is None:
                        raise RuntimeError("Matching CDC before-image is missing")
                    break
            time.sleep(1)

    if before is None or after is None:
        raise RuntimeError("Lab update not captured: check Agent, jobs, and database context")
    payload = {
        "payload": {
            "table": "appointments",
            "__$operation": 4,
            "key": {"appointment_id": after["appointment_id"]},
            "before": {key: before[key] for key in fields},
            "after": {key: after[key] for key in fields},
            "__$start_lsn": "0x" + bytes(after["__$start_lsn"]).hex(),
            "__$seqval": "0x" + bytes(after["__$seqval"]).hex(),
            "correlation_id": "sqlserver-live-lab",
        }
    }
    request = Request(
        "http://127.0.0.1:8000/api/ingest/sqlserver-cdc?persona=admin",
        data=json.dumps(payload, default=str).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        event = json.load(response)
    print("Ingested canonical event:", event["event_id"])
    print("Source:", event["source"], "capture method:", event["capture_method"])


if __name__ == "__main__":
    main()
