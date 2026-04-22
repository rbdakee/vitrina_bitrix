from __future__ import annotations

from datetime import datetime

from app.config import Settings
from app.services.lead_payload import LeadPayloadBuilder


def test_payload_builder_creates_stable_title_and_phone_payload():
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/vitrina",
        ADMIN_API_TOKEN="test-token",
        SKIP_STARTUP_VALIDATION="true",
    )
    builder = LeadPayloadBuilder(settings)
    row = {
        "vitrina_id": 123,
        "rbd_id": 456,
        "krisha_id": "K-1",
        "krisha_date": datetime(2026, 2, 1, 12, 30, 0),
        "object_type": "Квартира",
        "address": "Астана, ул. Тестовая 1",
        "complex": "Test Park",
        "builder": "Builder",
        "flat_type": "Евро",
        "property_class": "Бизнес",
        "condition": "Свежий ремонт",
        "sell_price": 50000000,
        "sell_price_per_m2": 600000,
        "house_num": "1",
        "floor_num": 4,
        "floor_count": 9,
        "room_count": 2,
        "phones": "+7 777 111 22 33; +7 777 111 22 33, +7 701 000 11 22",
        "description": "Подробное описание",
        "ceiling_height": 3.0,
        "area": 82.5,
        "year_built": 2024,
        "wall_type": "кирпич",
        "stats_object_status": None,
        "stats_description": "Важно перезвонить",
        "stats_object_category": "A",
    }

    snapshot = builder.build_snapshot(row)
    payload = builder.build_payload(row, bitrix_user_id="42")

    assert snapshot["krisha_date"] == "2026-02-01T12:30:00"
    assert payload["title"] == "[Vitrina] Квартира | Астана, ул. Тестовая 1 | ID 123"
    assert payload["assignedById"] == "42"
    assert payload["originId"] == "123"
    assert payload["phones"] == [
        {"value": "77771112233", "valueType": "WORK"},
        {"value": "77010001122", "valueType": "WORK"},
    ]
