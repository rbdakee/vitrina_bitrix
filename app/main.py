from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router, root_router
from app.config import Settings, get_settings
from app.db.session import DatabaseRuntime
from app.db.validators import validate_legacy_schema


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    runtime = DatabaseRuntime(settings)
    app.state.database_runtime = runtime
    app.state.session_factory = runtime.session_factory
    if not settings.skip_startup_validation:
        await validate_legacy_schema(runtime.session_factory)
    try:
        yield
    finally:
        await runtime.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    app = FastAPI(
        title="Vitrina Bitrix Backend",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.include_router(root_router)
    app.include_router(api_router)
    return app


app = create_app()

