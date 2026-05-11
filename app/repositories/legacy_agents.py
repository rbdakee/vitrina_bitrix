from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.legacy_tables import parsed_properties, vitrina_agents


class LegacyAgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_phone(self, agent_phone: str) -> dict[str, Any] | None:
        result = await self.session.execute(
            select(vitrina_agents).where(vitrina_agents.c.agent_phone == agent_phone)
        )
        row = result.mappings().first()
        if not row:
            return None
        return {
            "agent_phone": row["agent_phone"],
            "full_name": row["full_name"],
            "chat_ids": list(row["chat_ids"]) if row["chat_ids"] else [],
            "role": row["role"],
            "property_classes": list(row["property_classes"]) if row["property_classes"] else None,
        }

    async def get_property_classes(self, agent_phone: str) -> list[str] | None:
        result = await self.session.execute(
            select(vitrina_agents.c.property_classes).where(vitrina_agents.c.agent_phone == agent_phone)
        )
        value = result.scalar_one_or_none()
        return list(value) if value else None

    async def save_property_classes(self, agent_phone: str, property_classes: list[str]) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO vitrina_agents (agent_phone, property_classes, updated_at)
                VALUES (:agent_phone, :property_classes, NOW() AT TIME ZONE 'Asia/Almaty')
                ON CONFLICT (agent_phone)
                DO UPDATE SET
                    property_classes = :property_classes,
                    updated_at = NOW() AT TIME ZONE 'Asia/Almaty'
                """
            ),
            {
                "agent_phone": agent_phone,
                "property_classes": property_classes,
            },
        )
        await self.session.flush()

    async def clear_property_classes(self, agent_phone: str) -> None:
        await self.session.execute(
            text(
                """
                UPDATE vitrina_agents
                SET property_classes = NULL,
                    updated_at = NOW() AT TIME ZONE 'Asia/Almaty'
                WHERE agent_phone = :agent_phone
                """
            ),
            {"agent_phone": agent_phone},
        )
        await self.session.flush()

    async def get_distinct_property_classes(self) -> list[str]:
        result = await self.session.execute(
            select(parsed_properties.c.property_class)
            .where(parsed_properties.c.property_class.is_not(None))
            .distinct()
            .order_by(parsed_properties.c.property_class.asc())
        )
        return [row[0] for row in result.fetchall() if row[0]]

    async def list_phone_and_name(self) -> list[tuple[str, str | None]]:
        result = await self.session.execute(
            select(vitrina_agents.c.agent_phone, vitrina_agents.c.full_name)
        )
        return [(row[0], row[1]) for row in result.fetchall()]

    async def create_minimal(self, agent_phone: str, full_name: str | None) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO vitrina_agents (agent_phone, full_name, created_at, updated_at)
                VALUES (:agent_phone, :full_name, NOW() AT TIME ZONE 'Asia/Almaty', NOW() AT TIME ZONE 'Asia/Almaty')
                ON CONFLICT (agent_phone) DO NOTHING
                """
            ),
            {"agent_phone": agent_phone, "full_name": full_name},
        )
        await self.session.flush()

    async def exists(self, agent_phone: str) -> bool:
        result = await self.session.execute(
            select(func.count())
            .select_from(vitrina_agents)
            .where(vitrina_agents.c.agent_phone == agent_phone)
        )
        return bool(result.scalar_one())

