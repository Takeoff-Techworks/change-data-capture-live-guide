# Bonus: Python app integration with PostgreSQL CDC

Complete the [core PostgreSQL exercise](README.md) first and keep PostgreSQL and
the receiver running. This bonus uses a new **`northstar_app`** database and
seeds it through the same `app/seed.py` function. It does not migrate records
from SQLite or `northstar_cdc_lab`.

## 1. Create the application login and database

Stop the core connector while keeping PostgreSQL and the receiver running:

```text
docker compose -f docker/database-capture/compose.yaml stop debezium
```

Connect to the `postgres` database, then check that the names are unused. Use
the same app password in Step 2.

<details>
<summary>psql: switch database</summary>

```text
\connect postgres
```

</details>

<details>
<summary>VS Code: switch database</summary>

Open a query using the same server and credentials from the core exercise, with
Database set to `postgres`.

</details>

```sql
SELECT datname FROM pg_database WHERE datname = 'northstar_app';
SELECT rolname FROM pg_roles WHERE rolname = 'northstar_app';
```

If both return no rows:

```sql
CREATE ROLE northstar_app LOGIN PASSWORD 'northstar-app-lab-only';
CREATE DATABASE northstar_app OWNER northstar_app;
GRANT CONNECT ON DATABASE northstar_app TO debezium;
```

The `debezium` replication role already exists in the supplied lab.

## 2. Install the driver and select PostgreSQL

Stop any existing Uvicorn process. In a terminal using Python 3.12+ and the
existing `.venv`, run from the repository root:

```text
python -m pip install -e ".[dev,postgres]"
```

The launcher applies the lab settings to each command. Host tools use port
`15432`; containers use `postgres:5432`.

Verify the target before seeding:

```text
python exercises/03-postgres/postgres_cdc_bridge.py verify
python exercises/03-postgres/postgres_cdc_bridge.py seed
python exercises/03-postgres/postgres_cdc_bridge.py serve postgres
```

Expect `northstar_app` twice before seeding. Use a fresh app database.

Connect your SQL client to `northstar_app`, then run the verification query.

<details>
<summary>psql: switch database</summary>

```text
\connect northstar_app
```

</details>

<details>
<summary>VS Code: switch database</summary>

Open a query using the same host and port, with Database set to `northstar_app`.
Use user `northstar_app` and the password from Step 1.

</details>

```sql
SELECT count(*) AS patients FROM public.patients;
SELECT count(*) AS appointments FROM public.appointments;
SELECT patient_id, latest_appointment_status, priority_score
FROM public.care_work_queue ORDER BY patient_id;
```

Open `http://127.0.0.1:8000/reception?persona=admin` or the forwarded port 8000
URL. Cancel patient `p1`'s seeded appointment, then verify:

```sql
SELECT appointment_id, status, reason_code
FROM public.appointments WHERE appointment_id = 'appt1';
SELECT event_id, source, capture_method, status
FROM public.canonical_events ORDER BY captured_at DESC LIMIT 5;
```

Expect `appt1 = canceled` and a processed `simulated` event.

## 3. Capture the application's source table

Using an administrator SQL connection to `northstar_app`:

```sql
GRANT USAGE ON SCHEMA public TO debezium;
GRANT SELECT ON public.appointments TO debezium;
ALTER TABLE public.appointments REPLICA IDENTITY FULL;
CREATE PUBLICATION northstar_app_publication FOR TABLE public.appointments;
```

From the repository root in a host terminal:

```text
docker compose -f docker/database-capture/compose.yaml --profile app-capture up -d --pull never --no-build debezium-app
docker compose -f docker/database-capture/compose.yaml logs --tail=100 debezium-app
docker compose -f docker/database-capture/compose.yaml exec -T cdc-receiver cat ../data/events.jsonl
```

Search for `northstar_app`. Expect ten app snapshot rows. This service uses
`northstar_app_slot` and separate offsets.

## 4. Update the source directly

Run once in your SQL client:

```sql
UPDATE public.appointments
SET status = 'no_show', reason_code = 'postgres-live-lab',
    updated_at = clock_timestamp()
WHERE appointment_id = 'appt3' AND status = 'scheduled'
RETURNING appointment_id, patient_id, status;

SELECT a.appointment_id, a.status AS source_status,
       q.latest_appointment_status AS projected_status
FROM public.appointments AS a
JOIN public.care_work_queue AS q ON q.patient_id = a.patient_id
WHERE a.appointment_id = 'appt3';
```

Expect one updated row: source `no_show`, projection `scheduled`. Keep the app
running; the projection needs the captured event.

Repeat this read until the captured update arrives:

```text
docker compose -f docker/database-capture/compose.yaml exec -T cdc-receiver cat ../data/events.jsonl
```

Search for `postgres-live-lab`.

## 5. Forward the captured update

From the repository root in the same Python environment used in Step 2:

```text
docker compose -f docker/database-capture/compose.yaml exec -T cdc-receiver cat ../data/events.jsonl | python exercises/03-postgres/postgres_cdc_bridge.py forward --appointment-id appt3 --reason postgres-live-lab
```

The script posts the matching event to the local app. Use
`--app-url http://HOST:PORT` if the app is elsewhere. Run it once; repeated
forwarding creates another event.

Refresh **Diagnostics** and find the printed event ID. Expect source `postgres`,
capture method `debezium_postgres`, and status `processed`. If the consumer was
paused in the UI, resume/process it.

In your SQL client:

```sql
SELECT a.appointment_id, a.status AS source_status,
       q.latest_appointment_status AS projected_status,
       q.priority_score, q.priority_reasons_json
FROM public.appointments AS a
JOIN public.care_work_queue AS q ON q.patient_id = a.patient_id
WHERE a.appointment_id = 'appt3';
```

Expect both statuses to be `no_show`. **Nurse Queue** should show Cedar North
(`p3`) with a no-show reason. Direct SQL updates do not create workflow tasks.

## 6. Switch back to SQLite

Stop Uvicorn, then run:

```text
python exercises/03-postgres/postgres_cdc_bridge.py serve sqlite
```

This reopens the old SQLite file; it does not copy PostgreSQL changes back.
Avoid `scripts/reset_demo.py` against databases you intend to preserve: it drops
the app's tables.

To stop the bonus connector while retaining both databases, offsets, and the
event journal:

```text
docker compose -f docker/database-capture/compose.yaml --profile app-capture stop debezium-app
```

## Resources

- [Core PostgreSQL exercise](README.md)
- [App connector settings](../../docker/database-capture/debezium/application-app.properties)
- [PostgreSQL CDC bridge](postgres_cdc_bridge.py)
