import json
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import uuid4

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .cdc.consumer import duplicate_event, process_pending, refresh_state, state
from .cdc.dlq import write_dlq
from .cdc.normalizer import debezium_event, sqlserver_event
from .config import settings
from .db import SessionLocal, get_db, init_db
from .models import (
    Appointment,
    CanonicalEvent,
    CareTask,
    CareWorkQueue,
    DeadLetterEvent,
    Patient,
    Provider,
    RawCDCEvent,
    Referral,
    User,
)
from .schemas import AssistantRequest, IngestPayload
from .seed import seed_demo, utcnow
from .services.authorization_service import can_access_patient, persona, visible_patients
from .services.diagnostics_service import health, trace
from .services.policy_service import ask_assistant, assistant_provider_name
from .services.projection_service import recompute_patient
from .services.workflow_service import (
    create_appointment,
    create_referral,
    update_appointment,
    update_task,
)


def bootstrap() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_demo(db)
        for patient in db.scalars(select(Patient)).all():
            if not db.get(
                CareWorkQueue,
                patient.patient_id,
            ):
                event = CanonicalEvent(
                    event_id=f"seed-{patient.patient_id}",
                    raw_event_id=None,
                    source="simulated",
                    capture_method="simulated",
                    source_table="seed",
                    operation="c",
                    entity_key_json="{}",
                    before_json=None,
                    after_json=None,
                    patient_id=patient.patient_id,
                    source_commit_at=utcnow(),
                    captured_at=utcnow(),
                    schema_version=1,
                    correlation_id="seed",
                    status="processed",
                )
                db.add(event)
                db.flush()
                recompute_patient(db, patient.patient_id, event)
        refresh_state(db)
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap()
    yield


app = FastAPI(title="Northstar Care Coordination", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def user_for(request: Request, db: Session) -> User:
    return persona(
        db, request.query_params.get("persona", request.headers.get("x-demo-user", "admin"))
    )


def base_context(request: Request, db: Session, user: User, **extra):
    return {
        "request": request,
        "persona": user,
        "personas": list(db.scalars(select(User).order_by(User.full_name))),
        "health": health(db),
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(
        url=f"/reception?persona={request.query_params.get('persona', 'admin')}"
    )


@app.get("/reception", response_class=HTMLResponse)
def reception(request: Request, db: Session = Depends(get_db)):
    user = user_for(request, db)
    appointments = (
        db.execute(select(Appointment).order_by(Appointment.scheduled_start_at.desc()))
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="receptionist.html",
        context=base_context(
            request,
            db,
            user,
            appointments=appointments,
            patients=visible_patients(db, user),
            providers=list(db.scalars(select(Provider))),
        ),
    )


@app.post("/reception/appointments")
def add_appointment(
    request: Request,
    patient_id: str = Form(...),
    provider_id: str = Form(...),
    scheduled_start_at: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        create_appointment(db, patient_id, provider_id, datetime.fromisoformat(scheduled_start_at))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(
        url=f"/reception?persona={request.query_params.get('persona', 'admin')}", status_code=303
    )


@app.post("/reception/appointments/{appointment_id}/{action}")
def change_appointment(
    appointment_id: str, action: str, request: Request, db: Session = Depends(get_db)
):
    mapping = {"cancel": "canceled", "complete": "completed", "no_show": "no_show"}
    if action not in mapping:
        raise HTTPException(400, "Unknown appointment action")
    update_appointment(
        db,
        appointment_id,
        status=mapping[action],
        reason_code="canceled_by_reception" if action == "cancel" else None,
    )
    return RedirectResponse(
        url=f"/reception?persona={request.query_params.get('persona', 'admin')}", status_code=303
    )


@app.get("/nurse", response_class=HTMLResponse)
def nurse(request: Request, db: Session = Depends(get_db)):
    user = user_for(request, db)
    rows = [
        q
        for q in db.query(CareWorkQueue).order_by(CareWorkQueue.priority_score.desc()).all()
        if can_access_patient(db, user, q.patient_id)
    ]
    return templates.TemplateResponse(
        request=request,
        name="nurse.html",
        context=base_context(
            request, db, user, queue=rows, tasks=list(db.scalars(select(CareTask)))
        ),
    )


@app.post("/nurse/tasks/{task_id}/{action}")
def task_action(task_id: str, action: str, request: Request, db: Session = Depends(get_db)):
    if action not in {"complete", "reopen"}:
        raise HTTPException(400, "Unknown task action")
    update_task(db, task_id, status="completed" if action == "complete" else "open")
    return RedirectResponse(
        url=f"/nurse?persona={request.query_params.get('persona', 'admin')}", status_code=303
    )


@app.get("/clinician", response_class=HTMLResponse)
def clinician(request: Request, db: Session = Depends(get_db)):
    user = user_for(request, db)
    allowed = {p.patient_id for p in visible_patients(db, user)}
    referrals = [r for r in db.scalars(select(Referral)).all() if r.patient_id in allowed]
    return templates.TemplateResponse(
        request=request,
        name="clinician.html",
        context=base_context(
            request, db, user, patients=[p for p in visible_patients(db, user)], referrals=referrals
        ),
    )


@app.post("/clinician/referrals")
def add_referral(
    request: Request,
    patient_id: str = Form(...),
    specialty: str = Form(...),
    db: Session = Depends(get_db),
):
    user = user_for(request, db)
    provider = db.scalar(select(Provider).where(Provider.user_id == user.user_id))
    if not provider or not can_access_patient(db, user, patient_id):
        raise HTTPException(403, "Access unavailable")
    create_referral(db, patient_id, provider.provider_id, specialty)
    return RedirectResponse(url=f"/clinician?persona={user.user_id}", status_code=303)


@app.get("/assistant", response_class=HTMLResponse)
def assistant_view(request: Request, db: Session = Depends(get_db)):
    user = user_for(request, db)
    return templates.TemplateResponse(
        request=request,
        name="assistant.html",
        context=base_context(request, db, user, answer=None, provider=assistant_provider_name()),
    )


@app.post("/assistant", response_class=HTMLResponse)
def assistant_answer(
    request: Request,
    question: str = Form(...),
    patient_id: str | None = Form(None),
    db: Session = Depends(get_db),
):
    user = user_for(request, db)
    try:
        answer = ask_assistant(
            db, user.user_id, AssistantRequest(question=question, patient_id=patient_id or None)
        )
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return templates.TemplateResponse(
        request=request,
        name="assistant.html",
        context=base_context(request, db, user, answer=answer, provider=assistant_provider_name()),
    )


@app.get("/diagnostics", response_class=HTMLResponse)
def diagnostics(request: Request, db: Session = Depends(get_db)):
    user = user_for(request, db)
    if user.role != "admin":
        raise HTTPException(403, "Diagnostics is available to the admin demo persona")
    return templates.TemplateResponse(
        request=request,
        name="diagnostics.html",
        context=base_context(
            request,
            db,
            user,
            events=list(
                db.scalars(select(CanonicalEvent).order_by(CanonicalEvent.captured_at.desc()))
            ),
            dlq=list(
                db.scalars(select(DeadLetterEvent).order_by(DeadLetterEvent.created_at.desc()))
            ),
        ),
    )


def persist_ingested(db: Session, event, mode: str):
    raw_id = str(uuid4())
    db.add(
        RawCDCEvent(
            raw_event_id=raw_id,
            mode=mode,
            source_table=event.table,
            payload_json=event.model_dump_json(),
            received_at=utcnow(),
        )
    )
    db.add(
        CanonicalEvent(
            event_id=event.event_id,
            raw_event_id=raw_id,
            source=event.source,
            capture_method=event.capture_method,
            source_table=event.table,
            operation=event.operation,
            entity_key_json=json.dumps(event.entity_key),
            before_json=json.dumps(event.before, default=str) if event.before else None,
            after_json=json.dumps(event.after, default=str) if event.after else None,
            patient_id=event.patient_id,
            source_commit_at=event.source_commit_at,
            captured_at=event.captured_at,
            schema_version=event.schema_version,
            correlation_id=event.correlation_id,
            status="pending",
        )
    )
    db.commit()
    if settings.auto_process:
        process_pending(db)
    return event


def require_admin(request: Request, db: Session):
    if user_for(request, db).role != "admin":
        raise HTTPException(403, "Admin demo persona required")


@app.post("/api/ingest/sqlserver-cdc")
def ingest_sqlserver(body: IngestPayload, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    try:
        return persist_ingested(db, sqlserver_event(body.payload), "sqlserver").model_dump(
            mode="json"
        )
    except Exception as e:
        write_dlq(db, None, None, e, body.payload)
        db.commit()
        raise HTTPException(422, str(e))


@app.post("/api/ingest/debezium")
def ingest_debezium(body: IngestPayload, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    try:
        return persist_ingested(db, debezium_event(body.payload), "postgres_debezium").model_dump(
            mode="json"
        )
    except Exception as e:
        write_dlq(db, None, None, e, body.payload)
        db.commit()
        raise HTTPException(422, str(e))


@app.post("/api/cdc/process")
def api_process(request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    return {"processed": process_pending(db)}


@app.post("/api/cdc/pause")
def api_pause(request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    state(db).paused = True
    db.commit()
    return health(db)


@app.post("/api/cdc/resume")
def api_resume(request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    state(db).paused = False
    db.commit()
    return {"processed": process_pending(db)}


@app.post("/api/cdc/duplicate/{event_id}")
def api_duplicate(event_id: str, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    try:
        return {"event_id": duplicate_event(db, event_id).event_id}
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/api/cdc/replay-dlq/{dlq_id}")
def api_replay(dlq_id: str, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    item = db.get(DeadLetterEvent, dlq_id)
    if not item or not item.event_id:
        raise HTTPException(404, "Replayable DLQ event not found")
    event = db.get(CanonicalEvent, item.event_id)
    event.status = "pending"
    item.status = "replayed"
    item.replayed_at = utcnow()
    db.commit()
    return {"processed": process_pending(db)}


@app.get("/api/diagnostics/health")
def api_health(db: Session = Depends(get_db)):
    return health(db)


@app.get("/api/diagnostics/events/{event_id}")
def api_trace(event_id: str, db: Session = Depends(get_db)):
    result = trace(db, event_id)
    if not result:
        raise HTTPException(404, "Event not found")
    return result
