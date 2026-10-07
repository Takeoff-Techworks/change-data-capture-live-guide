import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.db import Base
from app.main import (
    app,
    assistant_answer,
    assistant_view,
    clinician,
    diagnostics,
    nurse,
    reception,
)
from app.seed import seed_demo


@pytest.mark.parametrize(
    "endpoint", [reception, nurse, clinician, assistant_view, assistant_answer, diagnostics]
)
def test_pages_render_html(endpoint):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    request = Request({"type": "http", "app": app, "query_string": b"", "headers": []})
    try:
        with Session(engine) as db:
            seed_demo(db)
            kwargs = {"request": request, "db": db}
            if endpoint is assistant_answer:
                kwargs.update(question="What tasks are open?", patient_id=None)
            response = endpoint(**kwargs)
            assert response.status_code == 200
            assert response.media_type == "text/html"
            assert b"Northstar" in response.body
    finally:
        engine.dispose()
