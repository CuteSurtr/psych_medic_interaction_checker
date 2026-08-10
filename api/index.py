"""Vercel serverless entry point for the NeuroTrace API.

Vercel discovers the ASGI application exported as `app` from this module and
routes every `/api/*` request to it (see `vercel.json`).

Two things differ from running `uvicorn main:app` locally:

1. `backend/` is put on `sys.path` so the existing absolute imports
   (`from database.connection import ...`) resolve unchanged.
2. The tables are created and seeded here at import time rather than relying
   on the FastAPI lifespan hook. Serverless invocations are short-lived and
   lifespan execution is not guaranteed by the platform adapter, so doing it
   at import makes cold-start seeding deterministic. With the default
   in-memory SQLite database this costs a few milliseconds per cold start and
   needs no external service.
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from database.seed_db import create_tables, seed_if_empty  # noqa: E402
from main import app  # noqa: E402

create_tables()
seed_if_empty()

__all__ = ["app"]
