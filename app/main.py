from fastapi import FastAPI

from app.api import control, review
from app.core.logging import setup_logging

setup_logging()
app = FastAPI(title="Company & Contact Discovery Pipeline")
app.include_router(review.router)
app.include_router(control.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
