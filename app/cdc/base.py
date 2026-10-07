from typing import Protocol

from sqlalchemy.orm import Session

from app.schemas import CanonicalChangeEvent


class CDCAdapter(Protocol):
    def ingest(self, db: Session, payload: dict) -> CanonicalChangeEvent: ...
