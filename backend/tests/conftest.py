import os

# Must be set before the app (and its engine) is imported.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://ughs:ughs_dev@localhost:5432/ughs_students_test",
)

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    yield
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE flagged_rows, roster_uploads, students, classes RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
