from fastapi import FastAPI

from zgrader.api.routers import admin, auth, catalog, submissions

app = FastAPI(title="ZGrader API", version="0.1.0")

app.include_router(auth.router)
app.include_router(submissions.router)
app.include_router(admin.router)
app.include_router(catalog.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
