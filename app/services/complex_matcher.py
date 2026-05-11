from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from app.bitrix.client import BitrixApiClient
from app.constants import BITRIX_SMART_COMPLEX_ENTITY_TYPE_ID
from app.schemas.bitrix import BitrixExecutionContext

_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_WS_RE = re.compile(r"\s+", re.UNICODE)

PAGE_SIZE = 50


def _normalize(name: str) -> str:
    if not name:
        return ""
    cleaned = _PUNCT_RE.sub(" ", name.lower())
    return _WS_RE.sub(" ", cleaned).strip()


class ComplexMatcher:
    def __init__(self, client: BitrixApiClient, cache_path: Path) -> None:
        self.client = client
        self.cache_path = cache_path
        self._lock = asyncio.Lock()
        self._index: dict[str, int] = {}
        self._next_start: int = 0
        self._exhausted: bool = False
        self._loaded: bool = False

    async def resolve(self, complex_name: str | None, context: BitrixExecutionContext) -> int | None:
        if not complex_name:
            return None
        async with self._lock:
            self._load_if_needed()
        return self._index.get(_normalize(complex_name))

    async def fetch_next_page(self, context: BitrixExecutionContext) -> dict[str, Any]:
        async with self._lock:
            self._load_if_needed()
            if self._exhausted:
                return {
                    "fetched": 0,
                    "added": 0,
                    "total_cached": len(self._index),
                    "next_start": self._next_start,
                    "exhausted": True,
                }

            response = await self.client.call_method(
                context,
                "crm.item.list",
                {
                    "entityTypeId": BITRIX_SMART_COMPLEX_ENTITY_TYPE_ID,
                    "select": ["id", "title"],
                    "start": self._next_start,
                },
            )
            data = response.get("result") or {}
            items = data.get("items") or []
            added = 0
            for item in items:
                title = (item.get("title") or "").strip()
                if not title:
                    continue
                key = _normalize(title)
                if not key or key in self._index:
                    continue
                self._index[key] = int(item["id"])
                added += 1

            fetched = len(items)
            next_value = response.get("next")
            if fetched < PAGE_SIZE or next_value is None:
                self._exhausted = True
            else:
                self._next_start = int(next_value)

            self._save()
            return {
                "fetched": fetched,
                "added": added,
                "total_cached": len(self._index),
                "next_start": self._next_start,
                "exhausted": self._exhausted,
            }

    def _load_if_needed(self) -> None:
        if self._loaded:
            return
        if self.cache_path.exists():
            with self.cache_path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
            self._index = {k: int(v) for k, v in (raw.get("index") or {}).items()}
            self._next_start = int(raw.get("next_start") or 0)
            self._exhausted = bool(raw.get("exhausted"))
        self._loaded = True

    def _save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(
                {
                    "index": self._index,
                    "next_start": self._next_start,
                    "exhausted": self._exhausted,
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )
        tmp.replace(self.cache_path)
