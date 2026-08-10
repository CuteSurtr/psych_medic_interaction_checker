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
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

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


# ---------------------------------------------------------------------------
# Single-page app
#
# Vercel routes every request to this application, not just /api/*, so the
# built frontend has to be served from here. A rewrite to /index.html does not
# work: the platform hands that path straight back to this app, which has no
# such route, and the result is a 404 on the site root.
#
# These routes are registered after `main` has attached the API routers, and
# FastAPI matches in registration order, so the catch-all below can never
# shadow an API endpoint.
# ---------------------------------------------------------------------------

DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
INDEX_HTML = DIST / "index.html"


@app.middleware("http")
async def _cache_headers(request, call_next):
    """Never cache the HTML shell; cache hashed assets forever.

    Vite emits a new content hash for the bundle on every build, and
    index.html is the only thing pointing at it. If a browser keeps a cached
    index.html across a deploy it asks for the previous hash, which no longer
    exists, the script 404s, and the page renders white with no error anyone
    can see. Marking the shell no-store makes a deploy take effect on the next
    request instead of stranding returning visitors.
    """
    response = await call_next(request)
    if request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

if (DIST / "assets").is_dir():
    # Vite emits content-hashed filenames, so these are safe to cache forever.
    app.mount(
        "/assets",
        StaticFiles(directory=str(DIST / "assets")),
        name="assets",
    )


@app.get("/{full_path:path}", include_in_schema=False)
async def _spa(full_path: str):
    """Serve the SPA shell for any non-API path so client-side routing works."""
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content=_not_found_payload("/" + full_path))

    candidate = (DIST / full_path) if full_path else None
    if candidate is not None and candidate.is_file():
        return FileResponse(candidate)

    if not INDEX_HTML.is_file():
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Frontend build output is missing from the deployment.",
                "expected": str(INDEX_HTML),
                "dist_exists": DIST.exists(),
                "hint": (
                    "The build must run `cd frontend && npm install && npm run "
                    "build`, and frontend/dist must be part of the function "
                    "bundle (see includeFiles in vercel.json)."
                ),
            },
        )
    return FileResponse(INDEX_HTML, media_type="text/html")


def _not_found_payload(path: str) -> dict:
    return {
        "detail": "Not Found",
        "received_path": path,
        "known_paths": sorted({getattr(r, "path", "") for r in app.routes})[:80],
    }


@app.exception_handler(404)
async def _not_found(request, exc):
    """404s that name the path the app actually received."""
    return JSONResponse(status_code=404, content=_not_found_payload(request.url.path))


__all__ = ["app"]
