from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BitrixAgentMapping


class BitrixAgentMappingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[BitrixAgentMapping]:
        result = await self.session.execute(
            select(BitrixAgentMapping).order_by(BitrixAgentMapping.bitrix_user_id.asc())
        )
        return list(result.scalars().all())

    async def get(self, bitrix_user_id: str) -> BitrixAgentMapping | None:
        result = await self.session.execute(
            select(BitrixAgentMapping).where(BitrixAgentMapping.bitrix_user_id == bitrix_user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        bitrix_user_id: str,
        agent_phone: str,
        full_name: str | None,
    ) -> BitrixAgentMapping:
        entity = BitrixAgentMapping(
            bitrix_user_id=bitrix_user_id,
            agent_phone=agent_phone,
            full_name=full_name,
        )
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, bitrix_user_id: str) -> bool:
        entity = await self.get(bitrix_user_id)
        if not entity:
            return False
        await self.session.delete(entity)
        await self.session.flush()
        return True

