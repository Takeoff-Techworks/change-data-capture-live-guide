from app.db import Base, engine, init_db
from app.main import bootstrap

Base.metadata.drop_all(engine)
init_db()
bootstrap()
print("Synthetic demo reset complete.")
