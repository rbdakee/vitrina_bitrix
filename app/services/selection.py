from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from app.constants import ASSIGNMENT_BATCH_SIZE, ASSIGNMENT_TARGETS

FetchIdsFn = Callable[[str, int, Sequence[int], Sequence[str] | None, bool], Awaitable[list[int]]]


class AssignmentSelector:
    def __init__(self, limit: int = ASSIGNMENT_BATCH_SIZE) -> None:
        self.limit = limit

    async def select(
        self,
        fetch_ids: FetchIdsFn,
        *,
        property_classes_filter: Sequence[str] | None,
        lock_rows: bool,
    ) -> tuple[list[int], dict[str, list[int]]]:
        ids_a = await self._fill_category(
            fetch_ids,
            category="A",
            limit_count=ASSIGNMENT_TARGETS["A"],
            exclude_ids=[],
            property_classes_filter=property_classes_filter,
            lock_rows=lock_rows,
        )

        missing_a = ASSIGNMENT_TARGETS["A"] - len(ids_a)
        needed_b = max(0, min(self.limit - len(ids_a), ASSIGNMENT_TARGETS["B"] + missing_a))
        ids_b = await self._fill_category(
            fetch_ids,
            category="B",
            limit_count=needed_b,
            exclude_ids=ids_a,
            property_classes_filter=property_classes_filter,
            lock_rows=lock_rows,
        )

        needed_c = max(0, self.limit - len(ids_a) - len(ids_b))
        ids_c = await self._fill_category(
            fetch_ids,
            category="C",
            limit_count=needed_c,
            exclude_ids=[*ids_a, *ids_b],
            property_classes_filter=property_classes_filter,
            lock_rows=lock_rows,
        )

        category_map = {"A": ids_a, "B": ids_b, "C": ids_c}
        return ids_a + ids_b + ids_c, category_map

    async def _fill_category(
        self,
        fetch_ids: FetchIdsFn,
        *,
        category: str,
        limit_count: int,
        exclude_ids: Sequence[int],
        property_classes_filter: Sequence[str] | None,
        lock_rows: bool,
    ) -> list[int]:
        if limit_count <= 0:
            return []

        selected: list[int] = []

        if property_classes_filter:
            selected = await fetch_ids(
                category,
                limit_count,
                list(exclude_ids),
                list(property_classes_filter),
                lock_rows,
            )

        remaining = limit_count - len(selected)
        if remaining > 0:
            additional = await fetch_ids(
                category,
                remaining,
                [*exclude_ids, *selected],
                None,
                lock_rows,
            )
            selected.extend(additional)

        return selected

