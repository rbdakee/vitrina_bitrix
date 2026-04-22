from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession


LEGACY_SCHEMA_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "parsed_properties": (
        "vitrina_id",
        "rbd_id",
        "krisha_id",
        "krisha_date",
        "object_type",
        "address",
        "complex",
        "builder",
        "flat_type",
        "property_class",
        "condition",
        "sell_price",
        "sell_price_per_m2",
        "house_num",
        "floor_num",
        "floor_count",
        "room_count",
        "phones",
        "description",
        "ceiling_height",
        "area",
        "year_built",
        "wall_type",
        "stats_agent_given",
        "stats_time_given",
        "stats_object_status",
        "stats_description",
        "stats_object_category",
        "updated_at",
    ),
    "vitrina_agents": (
        "agent_phone",
        "full_name",
        "property_classes",
    ),
}


async def _fetch_columns(session: AsyncSession, table_name: str) -> set[str]:
    result = await session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
            """
        ),
        {"table_name": table_name},
    )
    return {row.column_name for row in result.fetchall()}


def _find_missing(expected: Sequence[str], actual: set[str]) -> list[str]:
    return [column for column in expected if column not in actual]


async def validate_legacy_schema(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        for table_name, required_columns in LEGACY_SCHEMA_REQUIREMENTS.items():
            actual_columns = await _fetch_columns(session, table_name)
            if not actual_columns:
                raise RuntimeError(f"Required legacy table `{table_name}` is not available.")
            missing_columns = _find_missing(required_columns, actual_columns)
            if missing_columns:
                joined = ", ".join(missing_columns)
                raise RuntimeError(
                    f"Legacy table `{table_name}` is missing required columns: {joined}"
                )

