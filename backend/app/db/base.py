from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

Base = declarative_base()

_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable SQLite WAL mode, foreign keys, and busy timeout for high-concurrency read/write."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.close()


def get_engine() -> Engine:
    """Returns singleton SQLAlchemy Engine instance."""
    global _engine
    if _engine is None:
        db_path = settings.sqlite_db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{db_path.as_posix()}",
            connect_args={"check_same_thread": False},
            echo=False,
            future=True
        )
    return _engine


def get_session_factory() -> sessionmaker:
    """Returns singleton SessionFactory."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
    return _SessionFactory


def init_db() -> None:
    """Creates database tables and initializes schema."""
    engine = get_engine()
    from app.db import models as app_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    try:
        from db import models as db_models  # noqa: F401
        from db.database import Base as DbBase
        DbBase.metadata.create_all(bind=engine)
    except Exception:
        pass
