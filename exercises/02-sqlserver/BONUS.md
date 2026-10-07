# Bonus: Python app integration with SQL Server CDC

Complete the [core SQL Server CDC exercise](README.md) first and keep its SQL Server container running. Run commands from the repository root. This bonus exercise requires Python, a `.venv` virtual environment, and Microsoft ODBC Driver 18 (installed below). This section switches the app's storage from SQLite to SQL Server, then connects a real captured SQL update to the app's projection. It starts with fresh demo data; it does not migrate your existing SQLite records.

Use a new database named **`NorthstarApp`**. The SQL Server container's
`NorthstarSource` database is already initialized with the same source tables and
seed rows as the app. This bonus creates a separate app database from the shared
`app/seed.py` function, then points the app at it so app-owned event and
projection tables stay isolated. Keep the SQL Server container running.

There are two distinct paths to observe:

| Action | Source storage | How the app receives an event |
| --- | --- | --- |
| Click an action in Reception | SQL Server | The existing application workflow emits a simulated event |
| Update an appointment directly in SSMS | SQL Server | Native CDC captures it; the one-shot bridge below reads and posts that captured event |

`APP_DATABASE_URL` changes storage. `CDC_MODE` selects the demo mode label; it does not launch a SQL Server CDC polling service. Keep `CDC_MODE=simulated` for this mixed demonstration so the UI workflow is accurately labeled. An ingested native event still records `source=sqlserver` and `capture_method=sqlserver_cdc`.

## 1. Create the application's database and login

In your SQL session or SSMS, connect to the same container as `sa`. Check first that `NorthstarApp` and `northstar_app` are not already in use. If either exists, inspect it before continuing; do not overwrite an existing environment.

```sql
USE master;
GO
SELECT name FROM sys.databases WHERE name = N'NorthstarApp';
SELECT name FROM sys.server_principals WHERE name = N'northstar_app';
GO
```

When both checks return no rows, run the following, replacing the example password before execution:

```sql
CREATE DATABASE NorthstarApp;
GO
CREATE LOGIN northstar_app WITH PASSWORD = 'Replace-With-Your-Lab-Password!42';
GO
USE NorthstarApp;
GO
CREATE USER northstar_app FOR LOGIN northstar_app WITH DEFAULT_SCHEMA = dbo;
ALTER ROLE db_owner ADD MEMBER northstar_app;
GO
```

This login has ownership privileges only inside the disposable app database so it can create tables and run the lab's reads. Database-level CDC enablement later still uses your administrator connection. Use SQL Server authentication for this example; the instance must allow it.

## 2. Install the Python and ODBC dependencies

Stop the existing Uvicorn process with **Ctrl+C**. In the terminal where you run the app, change to the repository root and activate its virtual environment:

```bash
source .venv/bin/activate
python -m pip install -e '.[dev,sqlserver]'
```

The `sqlserver` extra installs `pyodbc`. Also install **Microsoft ODBC Driver 18 for SQL Server** in the operating system that runs Python. Use Microsoft's [Linux installation instructions](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server?view=sql-server-ver17), or its [driver downloads for Windows and macOS](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver17). Choose the instructions for your actual OS version. Installing the driver on your laptop does not install it inside a Codespace or development container.

Verify that Python can see it:

```bash
python - <<'PY'
import pyodbc
assert 'ODBC Driver 18 for SQL Server' in pyodbc.drivers(), pyodbc.drivers()
print('ODBC Driver 18 is available.')
PY
```

## 3. Select SQL Server and verify the connection

Run these Bash commands in the same terminal. Use the published SQL Server port from this exercise. These defaults assume Python and Docker run in the same host or development environment.

```bash
export SQLSERVER_HOST=127.0.0.1
export SQLSERVER_PORT=1435
export APP_DATABASE_URL="$(python - <<'PY'
import getpass
import os
from sqlalchemy import URL

url = URL.create(
    'mssql+pyodbc',
    username='northstar_app',
    password=getpass.getpass('northstar_app SQL login password: '),
    host=os.environ['SQLSERVER_HOST'],
    port=int(os.environ['SQLSERVER_PORT']),
    database='NorthstarApp',
    query={
        'driver': 'ODBC Driver 18 for SQL Server',
        'Encrypt': 'yes',
        'TrustServerCertificate': 'yes',
    },
)
print(url.render_as_string(hide_password=False))
PY
)"
export CDC_MODE=simulated
export CDC_AUTO_PROCESS=true
export CDC_CONSUMER_PAUSED=false
export CDC_FAILURE_MODE=none
```

`URL.create` handles password escaping. `TrustServerCertificate=yes` accommodates a self-signed lab certificate while using encryption; use certificate verification for a properly provisioned server. SQLAlchemy documents these options in its [SQL Server connection guide](https://docs.sqlalchemy.org/en/20/dialects/mssql.html#hostname-connections).

In a Codespace, run Docker and Python in that Codespace. If Docker runs on another host, replace `SQLSERVER_HOST` with its reachable network address; keep the published port `1435`. An environment file alone does not configure this app's standalone scripts: settings are read from process environment variables. Keep these exports in the terminal used for seeding and launching Uvicorn, and repeat them in a new terminal when needed.

Verify the selected database without printing the connection URL or password:

```bash
python - <<'PY'
from sqlalchemy import text
from app.db import engine

assert engine.dialect.name == 'mssql', 'APP_DATABASE_URL is not selecting SQL Server'
with engine.connect() as connection:
    row = connection.execute(text(
        'SELECT DB_NAME() AS database_name, SUSER_SNAME() AS login_name'
    )).mappings().one()
    assert row['database_name'] == 'NorthstarApp', row['database_name']
    print(dict(row))
PY
```

Expect `NorthstarApp` and `northstar_app`. Resolve driver, authentication, certificate, or network errors here before starting the app.

## 4. Create the app schema, seed it, and start the UI

From the repository root, with the same environment:

```bash
python scripts/seed_demo.py
python -m uvicorn app.main:app --reload
```

Startup uses SQLAlchemy to create the app's tables and seed predictable demo records. This repository now gives indexed string columns explicit lengths, uses a filtered unique index for nullable raw-event IDs on SQL Server, and inserts seed parent rows before their dependents. These changes are required for this database switch.

The setup targets a **fresh** SQL Server database. `create_all` does not migrate an older or partially created schema. Your SQLite file remains available for switching back later.

In your SQL session or SSMS, verify the application tables and seed:

```sql
USE NorthstarApp;
GO
SELECT COUNT(*) AS patients FROM dbo.patients;
SELECT COUNT(*) AS appointments FROM dbo.appointments;
SELECT appointment_id, patient_id, provider_id, status
FROM dbo.appointments ORDER BY appointment_id;
SELECT patient_id, latest_appointment_status, priority_score
FROM dbo.care_work_queue ORDER BY patient_id;
GO
```

Expect ten patients, ten appointments, and ten queue rows. In the browser, open `http://127.0.0.1:8000/reception?persona=admin` or the forwarded port 8000 URL for your Codespace.

Click **Cancel** for patient `p1`'s seeded appointment. Then query:

```sql
SELECT appointment_id, patient_id, status, reason_code
FROM dbo.appointments WHERE appointment_id = 'appt1';

SELECT TOP (5) event_id, source, capture_method, source_table, status
FROM dbo.canonical_events ORDER BY captured_at DESC;
GO
```

Expect `appt1 = canceled` and a processed event with `source = simulated`. Open **Diagnostics** to inspect it. You have now proved that UI writes, event storage, and projections are using SQL Server.

## 5. Enable native CDC on the app's appointments table

Using the administrator connection to the container, run this once against the new app database:

```sql
USE NorthstarApp;
GO
EXEC sys.sp_cdc_enable_db;
GO
EXEC sys.sp_cdc_enable_table
    @source_schema = N'dbo',
    @source_name = N'appointments',
    @capture_instance = N'app_appointments',
    @role_name = N'cdc_reader',
    @supports_net_changes = 0;
GO
EXEC sys.sp_cdc_help_jobs;
GO
```

Keep SQL Server Agent running. The capture instance here is **`app_appointments`**,
the same capture instance name used in `NorthstarSource` but isolated in the
`NorthstarApp` database. Capture only the source table for this experiment;
capturing the application's event and projection tables would introduce
unrelated changes into the stream.

Now make a direct SQL change to `appt3`, which starts as `scheduled` in a fresh app database:

```sql
SELECT appointment_id, status FROM dbo.appointments WHERE appointment_id = 'appt3';
GO
BEGIN TRANSACTION;
UPDATE dbo.appointments
SET status = 'no_show', reason_code = 'sqlserver-live-lab',
    updated_at = TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00')
WHERE appointment_id = 'appt3' AND status = 'scheduled';

IF @@ROWCOUNT <> 1
BEGIN
    ROLLBACK TRANSACTION;
    THROW 51010, 'Expected appt3 to be scheduled. Inspect its current state.', 1;
END;
COMMIT TRANSACTION;
GO
SELECT a.appointment_id, a.status AS source_status,
       q.latest_appointment_status AS projected_status
FROM dbo.appointments AS a
JOIN dbo.care_work_queue AS q ON q.patient_id = a.patient_id
WHERE a.appointment_id = 'appt3';
GO
```

Expect source status `no_show` and projected status `scheduled`. Reception reads the source table, so refreshing it shows the SQL update immediately. The queue has not been recomputed because the direct write bypassed the application workflow. Keep the app running without restarting it for the next step.

## 6. Forward the real captured event into the app

Open a **second repository terminal**, activate `.venv`, and repeat the database exports from step 3 there. Uvicorn keeps running in the first terminal. The [one-shot bridge script](sql_server_cdc_bridge.py) waits up to 60 seconds for the specific lab update, pairs its actual CDC images, and sends that captured data to the local ingestion endpoint.

This is a one-shot teaching bridge, not a continuous connector. Run it once after the update succeeds. It does not maintain a durable LSN checkpoint, and reposting creates another canonical event because the current normalizer assigns a new event ID on each request.

Run from the repository root, using the environment where you installed `.[dev,sqlserver]` in step 2:

```bash
source .venv/bin/activate
python exercises/02-sqlserver/sql_server_cdc_bridge.py
```

The submitted images are read from native CDC; they are not a hand-written fixture. Because the app now reads its source tables from **the same SQL Server database**, projection recomputation can see the changed appointment. The raw payload retains the LSN and sequence value; the existing normalizer still uses ingestion time for its canonical timestamps.

## 7. Verify the complete path

Refresh **Diagnostics**, find the event with source `sqlserver`, and inspect its raw payload, canonical record, processing log, and projection. If the consumer was paused in the UI, resume it and process pending events.

In your SQL session or SSMS:

```sql
USE NorthstarApp;
GO
SELECT TOP (5) event_id, source, capture_method, source_table, patient_id, status
FROM dbo.canonical_events
WHERE correlation_id = 'sqlserver-live-lab'
ORDER BY captured_at DESC;

SELECT a.appointment_id, a.status AS source_status,
       q.latest_appointment_status AS projected_status,
       q.priority_score, q.priority_reasons_json
FROM dbo.appointments AS a
JOIN dbo.care_work_queue AS q ON q.patient_id = a.patient_id
WHERE a.appointment_id = 'appt3';
GO
```

Expect a `processed` event with capture method `sqlserver_cdc`, and both statuses equal to `no_show`. Refresh **Nurse Queue** and locate Cedar North (`p3`); its priority reasons should now include the no-show without an active reschedule task. A direct SQL update does not execute the web workflow's task-creation logic, so the ingestion step recomputes the queue but does not create a reschedule task.

You have observed **SQL update → native CDC → one-shot ingestion → canonical event → queue projection**. Later SQL changes require another ingestion action; the application has no background SQL Server log reader. UI actions continue using the existing simulated capture path, even though they now write to SQL Server.

## 8. Troubleshooting and switching back

| Symptom | Check |
| --- | --- |
| `No module named pyodbc` | Activate the intended virtual environment and install `.[sqlserver]`. |
| ODBC driver cannot be opened | Install Driver 18 in the environment that runs Python and inspect `pyodbc.drivers()`. |
| Login timeout | Verify TCP access from the Codespace/container, server hostname, port, and SQL Server TCP configuration. |
| Login failed | Verify the SQL login, password, authentication mode, and database user. |
| Missing app columns or unexpected seed records | Confirm `DB_NAME() = NorthstarApp` and that `scripts/seed_demo.py` completed. |
| Invalid index key type or foreign-key error during setup | Use the updated model and seed code against a fresh database; `create_all` cannot repair a partial schema. |
| UI still appears to use SQLite | Stop the old Uvicorn process and restart from the terminal with the SQL Server exports. |
| Bridge times out | Inspect `NorthstarApp`'s Agent jobs and `sys.dm_cdc_errors`; verify the exact `appt3` update succeeded. |
| Ingested event remains pending | Resume the consumer in Diagnostics and process pending events. |
| Source updates but queue does not | A direct SQL write needs an ingested event before the projection recomputes. |

To return to your original SQLite demo, stop Uvicorn and use:

```bash
export APP_DATABASE_URL=sqlite:///./northstar.db
export CDC_MODE=simulated
python -m uvicorn app.main:app --reload
```

This reopens the existing SQLite file; it does not copy SQL Server changes back. Avoid `scripts/reset_demo.py` while connected to a database you intend to preserve: it drops the application's tables.

When finished, stop Uvicorn with Ctrl+C. To stop the SQL Server container while
preserving its databases and CDC history, run from the repository root:

```bash
docker compose -f docker/database-capture/compose.yaml stop sqlserver
```

Return to the [core walkthrough](README.md) for the seeded Northstar appointments exercise.
