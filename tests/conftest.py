from __future__ import annotations

import os

import pytest

from app.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    os.environ["SKIP_STARTUP_VALIDATION"] = "true"
    return Settings(
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/vitrina",
        ADMIN_API_TOKEN="test-token",
        BITRIX_ENABLED="false",
        SKIP_STARTUP_VALIDATION="true",
    )

