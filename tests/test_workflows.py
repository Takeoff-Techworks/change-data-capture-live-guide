from app.db import SessionLocal
from app.main import bootstrap
from app.models import CareTask
from app.services.workflow_service import update_appointment


def test_no_show_creates_one_reschedule_task():
    bootstrap()
    db = SessionLocal()
    try:
        update_appointment(db, "appt3", status="no_show")
        update_appointment(db, "appt3", status="no_show")
        assert (
            db.query(CareTask).filter_by(appointment_id="appt3", task_type="reschedule").count()
            == 1
        )
    finally:
        db.close()
