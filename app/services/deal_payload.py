from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.config import Settings
from app.constants import (
    BITRIX_DEAL_CURRENCY_ID,
    BITRIX_DEAL_SOURCE_DESCRIPTION,
    BITRIX_DEAL_SOURCE_ID,
    CONDITION_VALUE_TO_ENUM_ID,
    PROPERTY_TYPE_VALUE_TO_ENUM_ID,
    ROOMS_VALUE_TO_ENUM_ID,
    SNAPSHOT_FIELDS,
    TYPE_OFFER_SELL_ENUM_ID,
)


class DealPayloadBuilder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_snapshot(self, property_row: dict[str, Any]) -> dict[str, Any]:
        return {field: self._to_jsonable(property_row.get(field)) for field in SNAPSHOT_FIELDS}

    def build_payload(self, property_row: dict[str, Any], *, bitrix_user_id: str) -> dict[str, Any]:
        complex_name = (property_row.get("complex") or "").strip() or None
        address = (property_row.get("address") or "").strip() or None
        house_num = (str(property_row.get("house_num") or "")).strip() or None
        vitrina_id = property_row.get("vitrina_id")

        title_subject = complex_name or address or "Объект"
        title = f"[Vitrina] {title_subject} | ID {vitrina_id}"

        phones = self._extract_phones(property_row.get("phones"))
        contact_name = f"Объект {vitrina_id}" if vitrina_id is not None else "Объект"

        full_address = self._build_address(address, house_num)

        return {
            "title": title,
            "opportunity": self._to_jsonable(property_row.get("sell_price")),
            "currency_id": BITRIX_DEAL_CURRENCY_ID,
            "category_id": self.settings.bitrix_deal_category_id,
            "stage_id": self.settings.bitrix_deal_stage_id,
            "assigned_by_id": bitrix_user_id,
            "source_id": BITRIX_DEAL_SOURCE_ID,
            "source_description": BITRIX_DEAL_SOURCE_DESCRIPTION,
            "comments": self._build_comments(property_row),
            "complex_name": complex_name,
            "contact": {
                "name": contact_name,
                "phones": phones,
            },
            "uf": {
                "type_offer_id": TYPE_OFFER_SELL_ENUM_ID,
                "type_property_id": PROPERTY_TYPE_VALUE_TO_ENUM_ID.get(
                    (property_row.get("object_type") or "").strip()
                ),
                "condition_id": CONDITION_VALUE_TO_ENUM_ID.get(
                    (property_row.get("condition") or "").strip()
                ),
                "rooms_id": ROOMS_VALUE_TO_ENUM_ID.get(
                    self._room_count_key(property_row.get("room_count"))
                ),
                "floor": self._as_int(property_row.get("floor_num")),
                "floor_count": self._as_int(property_row.get("floor_count")),
                "area": self._as_int_rounded(property_row.get("area")),
                "year_built": self._as_int(property_row.get("year_built")),
                "sell_price": self._as_float(property_row.get("sell_price")),
                "address": full_address,
            },
        }

    def _build_address(self, address: str | None, house_num: str | None) -> str | None:
        if not address:
            return None
        if house_num:
            return f"{address}, {house_num}"
        return address

    def _build_comments(self, property_row: dict[str, Any]) -> str:
        krisha_id = property_row.get("krisha_id")
        krisha_url = f"https://krisha.kz/a/show/{krisha_id}" if krisha_id else None

        lines: list[tuple[str, Any]] = [
            ("Vitrina ID", property_row.get("vitrina_id")),
            ("RBD ID", property_row.get("rbd_id")),
            ("Krisha ID", property_row.get("krisha_id")),
            ("Krisha URL", krisha_url),
            ("Krisha date", self._to_jsonable(property_row.get("krisha_date"))),
            ("Застройщик", property_row.get("builder")),
            ("Класс объекта", property_row.get("property_class")),
            ("Цена за м²", property_row.get("sell_price_per_m2")),
            ("Высота потолков", property_row.get("ceiling_height")),
            ("Материал стен", property_row.get("wall_type")),
            ("Категория (A/B/C)", property_row.get("stats_object_category")),
            ("Статус по аналитике", property_row.get("stats_object_status")),
            ("Заметка агента", property_row.get("stats_description")),
            ("Описание объекта", property_row.get("description")),
        ]
        phones = self._extract_phones(property_row.get("phones"))
        if phones:
            lines.append(("Телефоны", ", ".join(phones)))

        rendered: list[str] = []
        for label, value in lines:
            if value in (None, "", []):
                continue
            rendered.append(f"{label}: {value}")
        return "\n".join(rendered)

    def _extract_phones(self, raw_phones: Any) -> list[str]:
        if not raw_phones:
            return []
        parts = re.split(r"[,;/\n]+", str(raw_phones))
        phones: list[str] = []
        seen: set[str] = set()
        for part in parts:
            digits = re.sub(r"\D+", "", part)
            if not digits or digits in seen:
                continue
            seen.add(digits)
            phones.append(digits)
        return phones

    def _room_count_key(self, value: Any) -> str | None:
        if value is None:
            return None
        try:
            return str(int(float(value)))
        except (TypeError, ValueError):
            text = str(value).strip()
            return text or None

    def _as_int(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _as_int_rounded(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None

    def _as_float(self, value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _to_jsonable(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return value
