from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.config import Settings
from app.constants import DEFAULT_BITRIX_ORIGINATOR_ID, DEFAULT_BITRIX_SOURCE_ID, SNAPSHOT_FIELDS


class LeadPayloadBuilder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_snapshot(self, property_row: dict[str, Any]) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        for field in SNAPSHOT_FIELDS:
            snapshot[field] = self._to_jsonable(property_row.get(field))
        return snapshot

    def build_payload(self, property_row: dict[str, Any], *, bitrix_user_id: str) -> dict[str, Any]:
        phones = self._extract_phones(property_row.get("phones"))
        payload: dict[str, Any] = {
            "title": (
                f"[Vitrina] {property_row.get('object_type') or 'Объект'} | "
                f"{property_row.get('address') or 'Без адреса'} | "
                f"ID {property_row.get('vitrina_id')}"
            ),
            "assignedById": bitrix_user_id,
            "sourceId": DEFAULT_BITRIX_SOURCE_ID,
            "sourceDescription": "Vitrina parsed property batch",
            "comments": self._build_comments(property_row),
            "originatorId": DEFAULT_BITRIX_ORIGINATOR_ID,
            "originId": str(property_row.get("vitrina_id")),
            "phones": [{"value": phone, "valueType": "WORK"} for phone in phones],
            "fm": {
                "PHONE": [{"VALUE": phone, "VALUE_TYPE": "WORK"} for phone in phones]
            },
        }

        if self.settings.bitrix_lead_stage_id:
            payload["stageId"] = self.settings.bitrix_lead_stage_id
        if self.settings.bitrix_lead_category_id:
            payload["categoryId"] = self.settings.bitrix_lead_category_id

        return payload

    def _build_comments(self, property_row: dict[str, Any]) -> str:
        lines = [
            f"Vitrina ID: {property_row.get('vitrina_id')}",
            f"RBD ID: {property_row.get('rbd_id') or '-'}",
            f"Krisha ID: {property_row.get('krisha_id') or '-'}",
            f"Address: {property_row.get('address') or '-'}",
            f"Complex: {property_row.get('complex') or '-'}",
            f"Builder: {property_row.get('builder') or '-'}",
            f"Class: {property_row.get('property_class') or '-'}",
            f"Condition: {property_row.get('condition') or '-'}",
            f"Price: {property_row.get('sell_price') or '-'}",
            f"Area: {property_row.get('area') or '-'}",
            f"Rooms: {property_row.get('room_count') or '-'}",
            f"Description: {property_row.get('description') or '-'}",
            f"Agent note: {property_row.get('stats_description') or '-'}",
        ]
        return "\n".join(lines)

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

    def _to_jsonable(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return value

