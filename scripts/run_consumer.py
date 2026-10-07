from app.cdc.consumer import process_pending
from app.db import SessionLocal

db = SessionLocal()
print(f"Processed {process_pending(db)} event(s).")
