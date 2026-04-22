from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.admin import router as admin_router
from app.api.routes.agents import router as agents_router
from app.api.routes.assignments import router as assignments_router
from app.api.routes.bitrix import api_router as bitrix_api_router
from app.api.routes.bitrix import ui_router as bitrix_ui_router
from app.api.routes.health import router as health_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(assignments_router)
api_router.include_router(agents_router)
api_router.include_router(admin_router)
api_router.include_router(bitrix_api_router)

root_router = APIRouter()
root_router.include_router(health_router)
root_router.include_router(bitrix_ui_router)

