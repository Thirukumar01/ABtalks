from typing import Generator
from sqlalchemy.orm import Session
from app.db.base import get_session_factory


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency injecting short-lived, transactional SQLite sessions.
    Automatically rolls back on uncaught errors and guarantees session disposal.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
