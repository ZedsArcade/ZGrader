import contextlib
import logging

from fastapi import FastAPI

from zgrader.api.routers import admin, auth, catalog, submissions
from zgrader.db import SessionLocal
from zgrader.seed import seed_all

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


app = FastAPI(title="Card Care Center API", version="0.1.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(submissions.router)
app.include_router(admin.router)
app.include_router(catalog.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
