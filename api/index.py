"""Vercel serverless entry point for the NeuroTrace API.

Vercel detects this project as a FastAPI backend and statically scans this
file for a module-level `app` bound to a FastAPI instance. That binding must
stay at the top level and unconditional: wrapping it in `try`/`except` hides
it from the scan and fails the build with

    Found api/index.py but it does not define a top-level "app" FastAPI
    instance.

so keep `from main import app` exactly where it is.

Two things differ from running `uvicorn main:app` locally:

1. `backend/` is put on `sys.path` so the existing absolute imports
   (`from database.connection import ...`) resolve unchanged.
2. Tables are created and seeded here at import time rather than relying on
   the FastAPI lifespan hook, since lifespan execution is not guaranteed by
   the platform adapter. With the default in-memory SQLite database this costs
   a few milliseconds per cold start and needs no external service.
"""

import sys
import traceback
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from main import app  # noqa: E402  - must stay top level, see module docstring

from database.seed_db import create_tables, seed_if_empty  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

# Seeding is the one startup step that touches state, so it is the one that can
# fail at runtime rather than import time. Report it instead of taking the
# whole function down: the traceback goes to stderr for `vercel logs`, and the
# endpoints that do not need seeded data keep working.
SEED_ERROR: str | None = None
try:
    create_tables()
    seed_if_empty()
except Exception:  # noqa: BLE001 - surface anything that breaks seeding
    SEED_ERROR = traceback.format_exc()
    print("NeuroTrace: seeding failed:\n" + SEED_ERROR, file=sys.stderr, flush=True)


@app.get("/api/__status")
def _status() -> dict:
    """Deployment self-check: confirms seeding ran and reports the route table."""
    return {
        "ok": SEED_ERROR is None,
        "seed_error": SEED_ERROR,
        "python": sys.version,
        "backend_on_path": str(BACKEND),
        "n_routes": len(app.routes),
    }


@app.exception_handler(404)
async def _not_found(request, exc):
    """404s that name the path the app actually received.

    Vercel warns that internal rewrites in backend-framework projects route on
    the *rewritten* destination. If that applies here the app would see
    `/api/index` instead of the requested route and every call would 404 for a
    non-obvious reason. Naming the arriving path makes that visible rather than
    looking like a missing endpoint.
    """
    return JSONResponse(
        status_code=404,
        content={
            "detail": "Not Found",
            "received_path": request.url.path,
            "hint": (
                "If received_path is '/api/index' rather than the route "
                "requested, the platform applied the vercel.json rewrite "
                "before the app saw the URL; drop the /api/(.*) rewrite."
            ),
            "known_paths": sorted({getattr(r, "path", "") for r in app.routes})[:80],
        },
    )


__all__ = ["app"]
