"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.backend.storage.local import LocalStorage

logger = logging.getLogger(__name__)

_CLEANUP_INTERVAL_HOURS = 6


async def _periodic_cleanup(store: LocalStorage) -> None:
    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL_HOURS * 3600)
        try:
            store.cleanup_expired()
            logger.info("Session cleanup complete.")
        except Exception:
            logger.exception("Session cleanup failed.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    store = LocalStorage()
    task = asyncio.create_task(_periodic_cleanup(store))
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="HTA API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from web.backend.api import sessions, dialogue, run, export  # noqa: E402

app.include_router(sessions.router, prefix="/api")
app.include_router(dialogue.router, prefix="/api")
app.include_router(run.router, prefix="/api")
app.include_router(export.router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
