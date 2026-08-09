import contextlib
import logging

from fastapi import FastAPI

from zgrader.api.routers import admin, auth, catalog, contact, submissions
from zgrader.config import config
from zgrader.db import SessionLocal
from zgrader.seed import seed_all

# Without this the API process has no logging configuration at all, so the
# root logger sits at WARNING and every logger.info() in the backend is
# dropped -- including the startup lines saying whether the admin bootstrap
# created, promoted or skipped an account. That made a real deployment
# problem undiagnosable from `docker logs`. The worker already does this
# (see zgrader/worker/main.py); the API simply never did.
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Idempotent -- ensures reference data and the optional bootstrap admin
    # (ZGRADER_ADMIN_EMAIL/PASSWORD) exist whenever the API starts, without
    # depending on the worker having run first.
    with SessionLocal() as db:
        try:
            seed_all(db)
        except Exception:  # noqa: BLE001 -- never block API startup on seeding
            logger.exception("Startup seeding failed")
    yield


# The interactive docs publish every route and schema, including the whole
# admin surface, to anyone who can reach the app -- and Next.js proxies
# /api/* straight through, so they'd be internet-facing. Useful in
# development, so they're only switched off in production.
_docs_enabled = config.env != "production"

app = FastAPI(
    title="Card Care Center API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

app.include_router(auth.router)
app.include_router(submissions.router)
app.include_router(admin.router)
app.include_router(catalog.router)
app.include_router(contact.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
