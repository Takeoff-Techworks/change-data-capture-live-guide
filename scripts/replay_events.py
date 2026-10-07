from app.cdc.consumer import process_pending
from app.db import SessionLocal

db = SessionLocal()
print(f"Replayed {process_pending(db)} pending event(s).")
