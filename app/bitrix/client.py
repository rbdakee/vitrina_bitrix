from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings
from app.constants import (
    BITRIX_TOOLBAR_PLACEMENT,
    UF_ADDRESS,
    UF_AREA,
    UF_COMPLEX_SMART,
    UF_CONDITION,
    UF_FLOOR,
    UF_FLOOR_COUNT,
    UF_ROOMS,
    UF_SELL_PRICE,
    UF_TYPE_OFFER,
    UF_TYPE_PROPERTY,
    UF_YEAR_BUILT,
)
from app.schemas.bitrix import BitrixExecutionContext

logger = logging.getLogger(__name__)


class BitrixApiClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def call_method(
        self,
        context: BitrixExecutionContext,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if not context.portal_domain or not context.access_token:
            raise ValueError("Bitrix portal_domain and access_token are required.")

        url = f"https://{context.portal_domain}/rest/{method}.json"
        logger.info("Bitrix call %s params=%s", method, params)
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(
                url,
                params={"auth": context.access_token},
                json=params,
            )
            try:
                payload = response.json()
            except ValueError:
                logger.error(
                    "Bitrix %s non-JSON response: status=%s body=%s",
                    method,
                    response.status_code,
                    response.text[:500],
                )
                response.raise_for_status()
                raise RuntimeError(f"Bitrix returned non-JSON response: {response.text}")
            if isinstance(payload, dict) and "error" in payload:
                error_code = str(payload.get("error") or "")
                description = payload.get("error_description") or error_code
                logger.error(
                    "Bitrix %s returned error: status=%s code=%s desc=%s",
                    method,
                    response.status_code,
                    error_code,
                    description,
                )
                raise RuntimeError(f"{error_code}: {description}" if error_code else description)
            response.raise_for_status()
            return payload

    async def bind_toolbar_placement(
        self,
        context: BitrixExecutionContext,
        handler_url: str,
    ) -> dict[str, Any]:
        return await self.call_method(
            context,
            "placement.bind",
            {
                "PLACEMENT": BITRIX_TOOLBAR_PLACEMENT,
                "HANDLER": handler_url,
                "TITLE": "Добавить 10 объектов",
                "DESCRIPTION": "Vitrina cold assignment",
            },
        )

    async def unbind_toolbar_placement(self, context: BitrixExecutionContext) -> dict[str, Any]:
        return await self.call_method(
            context,
            "placement.unbind",
            {"PLACEMENT": BITRIX_TOOLBAR_PLACEMENT},
        )

    async def fetch_deal_stages(
        self,
        context: BitrixExecutionContext,
        ids: list[str],
    ) -> dict[str, str | None]:
        if not ids:
            return {}

        result: dict[str, str | None] = {}
        batch_size = 50
        for start in range(0, len(ids), batch_size):
            batch = ids[start : start + batch_size]
            response = await self.call_method(
                context,
                "crm.deal.list",
                {
                    "filter": {"ID": batch},
                    "select": ["ID", "STAGE_SEMANTIC_ID"],
                },
            )
            deals = response.get("result") or []
            returned: dict[str, str | None] = {}
            for deal in deals:
                deal_id = deal.get("ID")
                if deal_id is None:
                    continue
                returned[str(deal_id)] = deal.get("STAGE_SEMANTIC_ID")
            for lead_id in batch:
                result[lead_id] = returned.get(lead_id)
        return result

    async def create_contact(
        self,
        context: BitrixExecutionContext,
        *,
        name: str,
        phones: list[str],
    ) -> str:
        fields: dict[str, Any] = {"NAME": name}
        if phones:
            fields["PHONE"] = [{"VALUE": phone, "VALUE_TYPE": "WORK"} for phone in phones]
        response = await self.call_method(context, "crm.contact.add", {"fields": fields})
        return str(response["result"])

    async def create_deal_with_contact(
        self,
        context: BitrixExecutionContext,
        *,
        payload: dict[str, Any],
        complex_smart_id: int | None,
    ) -> str:
        contact_info = payload.get("contact") or {}
        contact_phones = list(contact_info.get("phones") or [])
        contact_name = contact_info.get("name") or "Vitrina contact"
        contact_id = await self.create_contact(
            context, name=contact_name, phones=contact_phones
        )

        comments = payload.get("comments") or ""
        if complex_smart_id is None and payload.get("complex_name"):
            extra = f"ЖК (не сматчен): {payload['complex_name']}"
            comments = f"{comments}\n{extra}" if comments else extra

        fields: dict[str, Any] = {
            "TITLE": payload["title"],
            "ASSIGNED_BY_ID": payload["assigned_by_id"],
            "CONTACT_ID": contact_id,
            "SOURCE_ID": payload["source_id"],
            "SOURCE_DESCRIPTION": payload.get("source_description") or "",
            "CURRENCY_ID": payload.get("currency_id") or "KZT",
            "COMMENTS": comments,
        }
        if payload.get("opportunity") is not None:
            fields["OPPORTUNITY"] = payload["opportunity"]
        if payload.get("category_id"):
            fields["CATEGORY_ID"] = payload["category_id"]
        if payload.get("stage_id"):
            fields["STAGE_ID"] = payload["stage_id"]

        uf = payload.get("uf") or {}
        uf_map: dict[str, Any] = {
            UF_TYPE_OFFER: uf.get("type_offer_id"),
            UF_TYPE_PROPERTY: uf.get("type_property_id"),
            UF_CONDITION: uf.get("condition_id"),
            UF_ROOMS: uf.get("rooms_id"),
            UF_FLOOR: uf.get("floor"),
            UF_FLOOR_COUNT: uf.get("floor_count"),
            UF_AREA: uf.get("area"),
            UF_YEAR_BUILT: uf.get("year_built"),
            UF_SELL_PRICE: uf.get("sell_price"),
            UF_ADDRESS: uf.get("address"),
        }
        for code, value in uf_map.items():
            if value is None or value == "":
                continue
            fields[code] = value
        if complex_smart_id is not None:
            fields[UF_COMPLEX_SMART] = complex_smart_id

        response = await self.call_method(context, "crm.deal.add", {"fields": fields})
        return str(response["result"])
