from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import control, review
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.jobs import threaded

setup_logging()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if get_settings().QUEUE_MODE == "thread":
        threaded.start()
    yield
    threaded.stop()


app = FastAPI(title="Company & Contact Discovery Pipeline", lifespan=lifespan)
app.include_router(review.router)
app.include_router(control.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
