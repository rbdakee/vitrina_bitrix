from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.services.selection import AssignmentSelector


@dataclass(frozen=True)
class Candidate:
    vitrina_id: int
    category: str | None
    property_class: str | None
    krisha_date: datetime | None


def _make_candidate(
    vitrina_id: int,
    category: str | None,
    property_class: str | None,
    days_offset: int,
) -> Candidate:
    return Candidate(
        vitrina_id=vitrina_id,
        category=category,
        property_class=property_class,
        krisha_date=datetime(2026, 1, 1, 9, 0, 0) + timedelta(days=days_offset),
    )


def _sorted_supply(candidates: list[Candidate]) -> list[Candidate]:
    return sorted(
        candidates,
        key=lambda item: (
            item.krisha_date is not None,
            item.krisha_date or datetime.min,
            item.vitrina_id,
        ),
        reverse=True,
    )


def _build_fetcher(candidates: list[Candidate]):
    supply = _sorted_supply(candidates)

    async def fetch_ids(
        category: str,
        limit_count: int,
        exclude_ids: list[int],
        property_classes: list[str] | None,
        lock_rows: bool,
    ) -> list[int]:
        del lock_rows
        results: list[int] = []
        for candidate in supply:
            normalized_category = candidate.category or "C"
            if normalized_category != category:
                continue
            if candidate.vitrina_id in exclude_ids or candidate.vitrina_id in results:
                continue
            if property_classes and candidate.property_class not in property_classes:
                continue
            results.append(candidate.vitrina_id)
            if len(results) >= limit_count:
                break
        return results

    return fetch_ids


def test_selector_keeps_exact_3_3_4_distribution_when_supply_exists():
    selector = AssignmentSelector()
    fetcher = _build_fetcher(
        [
            _make_candidate(110, "A", "Business", 10),
            _make_candidate(109, "A", "Business", 9),
            _make_candidate(108, "A", "Comfort", 8),
            _make_candidate(210, "B", "Business", 10),
            _make_candidate(209, "B", "Comfort", 9),
            _make_candidate(208, "B", "Comfort", 8),
            _make_candidate(310, "C", "Business", 10),
            _make_candidate(309, None, "Business", 9),
            _make_candidate(308, "C", "Comfort", 8),
            _make_candidate(307, None, "Comfort", 7),
        ]
    )

    selected_ids, categories = asyncio.run(
        selector.select(fetcher, property_classes_filter=None, lock_rows=False)
    )

    assert len(selected_ids) == 10
    assert categories["A"] == [110, 109, 108]
    assert categories["B"] == [210, 209, 208]
    assert categories["C"] == [310, 309, 308, 307]


def test_selector_moves_missing_a_quota_into_b_then_c():
    selector = AssignmentSelector()
    fetcher = _build_fetcher(
        [
            _make_candidate(101, "A", "Business", 2),
            _make_candidate(201, "B", "Business", 9),
            _make_candidate(200, "B", "Business", 8),
            _make_candidate(199, "B", "Business", 7),
            _make_candidate(198, "B", "Business", 6),
            _make_candidate(301, "C", "Business", 5),
            _make_candidate(300, None, "Business", 4),
            _make_candidate(299, "C", "Business", 3),
            _make_candidate(298, None, "Business", 2),
            _make_candidate(297, "C", "Business", 1),
        ]
    )

    selected_ids, categories = asyncio.run(
        selector.select(fetcher, property_classes_filter=None, lock_rows=False)
    )

    assert len(selected_ids) == 10
    assert categories["A"] == [101]
    assert categories["B"] == [201, 200, 199, 198]
    assert categories["C"] == [301, 300, 299, 298, 297]


def test_selector_prefers_filtered_classes_then_tops_up_without_filter():
    selector = AssignmentSelector()
    fetcher = _build_fetcher(
        [
            _make_candidate(120, "A", "Business", 8),
            _make_candidate(119, "A", "Comfort", 7),
            _make_candidate(118, "A", "Comfort", 6),
            _make_candidate(220, "B", "Business", 8),
            _make_candidate(219, "B", "Comfort", 7),
            _make_candidate(218, "B", "Comfort", 6),
            _make_candidate(320, None, "Business", 8),
            _make_candidate(319, "C", "Comfort", 7),
            _make_candidate(318, "C", "Comfort", 6),
            _make_candidate(317, None, "Comfort", 5),
        ]
    )

    selected_ids, categories = asyncio.run(
        selector.select(
            fetcher,
            property_classes_filter=["Business"],
            lock_rows=False,
        )
    )

    assert len(selected_ids) == 10
    assert categories["A"] == [120, 119, 118]
    assert categories["B"] == [220, 219, 218]
    assert categories["C"] == [320, 319, 318, 317]
