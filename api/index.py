"""Vercel serverless entry point for the NeuroTrace API.

Vercel discovers the ASGI application exported as `app` and routes every
`/api/*` request to it (see `vercel.json`).

Two things differ from running `uvicorn main:app` locally:

1. `backend/` is put on `sys.path` so the existing absolute imports
   (`from database.connection import ...`) resolve unchanged. `vercel.json`
   must carry `includeFiles: "backend/**"` or that directory will not be in
   the function bundle at all.
2. The tables are created and seeded here at import time rather than relying
   on the FastAPI lifespan hook. Serverless invocations are short-lived and
   lifespan execution is not guaranteed by the platform adapter, so doing it
   at import makes cold-start seeding deterministic. With the default
   in-memory SQLite database this costs a few milliseconds per cold start and
   needs no external service.

If startup fails, the platform would otherwise return an opaque
FUNCTION_INVOCATION_FAILED. Instead the traceback is written to stderr (where
it shows up in `vercel logs`) and served as plain text by a dependency-free
fallback ASGI app, so the cause is visible in the browser even when the
failure is a missing dependency.
"""

import sys
import traceback
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

try:
    from database.seed_db import create_tables, seed_if_empty
    from main import app

    create_tables()
    seed_if_empty()

except Exception:  # noqa: BLE001 - report anything that stops the app booting
    _TRACEBACK = traceback.format_exc()
    print("NeuroTrace API failed to start:\n" + _TRACEBACK, file=sys.stderr, flush=True)

    def _diagnostics() -> str:
        lines = [
            "NeuroTrace API failed to start.",
            "",
            _TRACEBACK,
            "--- environment ---",
            f"python: {sys.version}",
            f"entry:  {Path(__file__).resolve()}",
            f"backend path: {BACKEND}",
            f"backend exists: {BACKEND.exists()}",
        ]
        if BACKEND.exists():
            names = sorted(p.name for p in BACKEND.iterdir())
            lines.append(f"backend contents: {', '.join(names)}")
        else:
            lines.append(
                "backend/ is missing from the function bundle. Check that "
                'vercel.json sets functions."api/index.py".includeFiles to '
                '"backend/**".'
            )
        lines.append("")
        lines.append("sys.path:")
        lines.extend(f"  {p}" for p in sys.path)
        return "\n".join(lines)

    # Plain ASGI, no imports: this has to work even when the failure was an
    # ImportError on FastAPI itself.
    async def app(scope, receive, send):  # type: ignore[misc]
        if scope["type"] != "http":
            return
        body = _diagnostics().encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


__all__ = ["app"]
