from pathlib import Path
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .config import ROOT
from .models import Base

path = Path(os.getenv("CORTEX_DB_PATH", "backend/data/cortex_lock.db"))
if not path.is_absolute():
    path = ROOT / path
path.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(
    "sqlite:///" + str(path), connect_args={"check_same_thread": False, "timeout": 15}
)


@event.listens_for(engine, "connect")
def configure(dbapi_connection, _):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")
    dbapi_connection.execute("PRAGMA busy_timeout=15000")


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    Base.metadata.create_all(engine)


def get_db():
    with SessionLocal() as db:
        yield db
