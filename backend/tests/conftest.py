import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.base import Base
from app.dependencies import get_db
from app.main import app

# In-memory SQLite with StaticPool ensures isolated, in-memory execution for fast unit tests
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=test_engine)
    try:
        from db import models as db_models  # noqa: F401
        from db.database import Base as DbBase
        DbBase.metadata.create_all(bind=test_engine)
    except Exception:
        pass

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        try:
            from db.database import Base as DbBase
            DbBase.metadata.drop_all(bind=test_engine)
        except Exception:
            pass


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
