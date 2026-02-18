"""FastAPI application entry point for the migration backend."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from api.routers.machines import router as machines_router
from api.routers.processing import direct_router as processing_direct_router
from api.routers.processing import router as processing_router
from api.routers.quotes import router as quotes_router
from api.routers.reports import router as reports_router
from api.routers.shipping import router as shipping_router
from api.routers.cor import router as cor_router


def _parse_cors_origins(raw_origins: str | None) -> list[str]:
    """Return a clean list of CORS origins from env var value."""
    if not raw_origins:
        return ["http://localhost:3000", "http://127.0.0.1:3000"]
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize runtime dependencies once on startup."""
    from src.utils.db import init_db

    init_db()
    yield


app = FastAPI(
    title="GOA LLM API",
    version="0.1.0",
    lifespan=lifespan,
)

cors_origins = _parse_cors_origins(os.getenv("CORS_ORIGINS"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["content-disposition", "content-type"],
)


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Simple liveness endpoint."""
    return {"status": "ok"}


app.include_router(quotes_router)
app.include_router(machines_router)
app.include_router(processing_router)
app.include_router(processing_direct_router)
app.include_router(reports_router)
app.include_router(shipping_router)
app.include_router(cor_router)
