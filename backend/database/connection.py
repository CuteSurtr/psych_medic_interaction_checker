"""Database engine and session factory.

The reference data (medications, CYP450 profiles, interactions) is static and
seeded from `seed_data.py`, so the default configuration is an in-memory
SQLite database that is rebuilt on process start. That makes the API run with
no external services, which is what the serverless deployment needs.

Set DATABASE_URL to a Postgres URL to get durable storage instead; the Docker
Compose stack does exactly that.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from config import DATABASE_URL


def _make_engine(url: str):
    if not url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True)

    # SQLite needs the thread check relaxed because FastAPI serves requests
    # from a worker threadpool. An in-memory database additionally needs
    # StaticPool: every connection in the default pool would otherwise get its
    # own private, empty database.
    kwargs = {"connect_args": {"check_same_thread": False}}
    if ":memory:" in url or url in ("sqlite://", "sqlite:///"):
        kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


engine = _make_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
