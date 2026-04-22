from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import and_, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ALMATY_TIMEZONE, NON_REALIZED_STATUSES, SNAPSHOT_FIELDS
from app.db.legacy_tables import parsed_properties


class ParsedPropertyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_non_realized(self, agent_phone: str) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(parsed_properties)
            .where(
                parsed_properties.c.stats_agent_given == agent_phone,
                parsed_properties.c.krisha_id.is_not(None),
                parsed_properties.c.krisha_id != "",
                parsed_properties.c.stats_object_status.in_(NON_REALIZED_STATUSES),
            )
        )
        return int(result.scalar_one() or 0)

    async def fetch_candidate_ids(
        self,
        *,
        category: str,
        limit_count: int,
        exclude_ids: Sequence[int],
        property_classes: Sequence[str] | None,
        lock_rows: bool,
    ) -> list[int]:
        if limit_count <= 0:
            return []

        conditions = [
            parsed_properties.c.krisha_id.is_not(None),
            parsed_properties.c.krisha_id != "",
            parsed_properties.c.stats_agent_given.is_(None),
        ]

        if category == "C":
            conditions.append(
                or_(
                    parsed_properties.c.stats_object_category == "C",
                    parsed_properties.c.stats_object_category.is_(None),
                )
            )
        else:
            conditions.append(parsed_properties.c.stats_object_category == category)

        if property_classes:
            conditions.append(parsed_properties.c.property_class.in_(list(property_classes)))

        if exclude_ids:
            conditions.append(parsed_properties.c.vitrina_id.not_in(list(exclude_ids)))

        statement = (
            select(parsed_properties.c.vitrina_id)
            .where(and_(*conditions))
            .order_by(
                desc(parsed_properties.c.krisha_date).nulls_last(),
                desc(parsed_properties.c.vitrina_id),
            )
            .limit(limit_count)
        )

        if lock_rows:
            statement = statement.with_for_update(skip_locked=True)

        result = await self.session.execute(statement)
        return [row[0] for row in result.fetchall()]

    async def fetch_rows_by_ids(self, ids: Sequence[int]) -> list[dict[str, Any]]:
        if not ids:
            return []

        columns = [parsed_properties.c[field] for field in SNAPSHOT_FIELDS]
        result = await self.session.execute(
            select(*columns).where(parsed_properties.c.vitrina_id.in_(list(ids)))
        )
        rows = [dict(row._mapping) for row in result.fetchall()]
        by_id = {row["vitrina_id"]: row for row in rows}
        return [by_id[item_id] for item_id in ids if item_id in by_id]

    async def mark_assigned(self, ids: Sequence[int], agent_phone: str) -> None:
        if not ids:
            return

        await self.session.execute(
            update(parsed_properties)
            .where(parsed_properties.c.vitrina_id.in_(list(ids)))
            .values(
                stats_agent_given=agent_phone,
                stats_time_given=func.timezone(ALMATY_TIMEZONE, func.now()),
                stats_object_status="Не позвонили",
                updated_at=func.now(),
            )
        )
        await self.session.flush()

