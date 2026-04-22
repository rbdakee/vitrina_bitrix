from __future__ import annotations

ASSIGNMENT_BATCH_SIZE = 10
ASSIGNMENT_LIMIT_THRESHOLD = 15
ALMATY_TIMEZONE = "Asia/Almaty"
BITRIX_TOOLBAR_PLACEMENT = "CRM_LEAD_LIST_TOOLBAR"
BITRIX_TOOLBAR_PLACEMENT_HANDLER = "/bitrix/toolbar"
DEFAULT_BITRIX_SOURCE_ID = "WEB"
DEFAULT_BITRIX_ORIGINATOR_ID = "vitrina_bitrix"

NON_REALIZED_STATUSES = (
    "Не позвонили",
    "Перезвонить",
    "Недозвон",
    "Встреча",
)

REALIZED_STATUSES = (
    "Договор",
    "Отказ",
    "Архив",
)

ASSIGNMENT_STATUS_PREVIEW = "preview"
ASSIGNMENT_STATUS_ASSIGNED = "assigned"
ASSIGNMENT_STATUS_BLOCKED_LIMIT = "blocked_limit"
ASSIGNMENT_STATUS_EMPTY_SUPPLY = "empty_supply"
ASSIGNMENT_STATUS_FAILED = "failed"

SYNC_STATUS_NOT_REQUESTED = "not_requested"
SYNC_STATUS_PENDING = "pending"
SYNC_STATUS_SUCCESS = "success"
SYNC_STATUS_PARTIAL_FAILED = "partial_failed"
SYNC_STATUS_FAILED = "failed"

ASSIGNMENT_TARGETS = {
    "A": 3,
    "B": 3,
    "C": 4,
}

SNAPSHOT_FIELDS = (
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
    "stats_object_status",
    "stats_description",
    "stats_object_category",
)

