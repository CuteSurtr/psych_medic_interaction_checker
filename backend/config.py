import os

# In-memory SQLite by default: the reference data is static and re-seeded at
# startup, so the API runs with no external services. Docker Compose and any
# durable deployment override this with a Postgres URL.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite://")

# Comma-separated list of allowed browser origins. On Vercel the SPA and the
# API share an origin, so this only matters for split deployments and local
# development.
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:80,http://frontend:80",
    ).split(",")
    if o.strip()
]
