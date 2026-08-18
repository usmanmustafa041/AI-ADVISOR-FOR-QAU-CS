"""Integration tests; run with RUN_DB_TESTS=1 after docker compose up."""

import os

import pytest
from sqlalchemy import create_engine, text


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="Set RUN_DB_TESTS=1 to run against the initialized PostgreSQL service",
)


def test_schema_and_seed_are_available() -> None:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://qau_advisor:qau_advisor_local@localhost:5432/qau_advisor",
    )
    engine = create_engine(url, connect_args={"connect_timeout": 3})
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM programs")).scalar_one() >= 5
        assert connection.execute(text("SELECT COUNT(*) FROM course_prerequisites WHERE verified")).scalar_one() == 2
        assert connection.execute(text("SELECT extname FROM pg_extension WHERE extname='vector'")).scalar_one() == "vector"

