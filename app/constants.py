from __future__ import annotations

ASSIGNMENT_BATCH_SIZE = 10
ASSIGNMENT_LIMIT_THRESHOLD = 15
ALMATY_TIMEZONE = "Asia/Almaty"

BITRIX_TOOLBAR_PLACEMENT = "CRM_DEAL_LIST_TOOLBAR"
BITRIX_TOOLBAR_PLACEMENT_HANDLER = "/bitrix/toolbar"

BITRIX_DEAL_SOURCE_ID = "PARSING"
BITRIX_DEAL_SOURCE_DESCRIPTION = "Parsed objects from RBD"
BITRIX_DEAL_CURRENCY_ID = "KZT"
BITRIX_SMART_COMPLEX_ENTITY_TYPE_ID = 1072

UF_TYPE_OFFER = "UF_CRM_1773916681"
UF_TYPE_PROPERTY = "UF_CRM_683441F286AE2"
UF_CONDITION = "UF_CRM_1734613640931"
UF_ROOMS = "UF_CRM_1736372188519"
UF_FLOOR = "UF_CRM_682EB4ED0F11D"
UF_FLOOR_COUNT = "UF_CRM_682EB4ED218EC"
UF_AREA = "UF_CRM_682EB4ECB2E67"
UF_YEAR_BUILT = "UF_CRM_682EB4ED32EC8"
UF_SELL_PRICE = "UF_CRM_1776612888"
UF_COMPLEX_SMART = "UF_CRM_1774623135"
UF_ADDRESS = "UF_CRM_OBJECTDEALADRESS"

TYPE_OFFER_SELL_ENUM_ID = 46545

PROPERTY_TYPE_VALUE_TO_ENUM_ID: dict[str, int] = {
    "Квартира": 29028,
    "Дом": 29030,
    "Коммерческая недвижимость": 29032,
    "Паркинг": 29034,
    "Земельный участок": 29036,
}

CONDITION_VALUE_TO_ENUM_ID: dict[str, int] = {
    "Хорошее состояние": 271,
    "Черновая отделка": 267,
    "Евроремонт": 273,
    "Требует ремонта": 269,
}

ROOMS_VALUE_TO_ENUM_ID: dict[str, int] = {
    "1": 1183,
    "2": 1185,
    "3": 1187,
    "4": 1189,
    "5": 1191,
    "6": 51663,
    "7": 51665,
    "8": 51667,
    "9": 51669,
    "10": 51671,
    "11": 51673,
    "12": 51675,
    "13": 51677,
    "14": 51679,
    "15": 51681,
}

BITRIX_STATUS_IN_PROGRESS = "В работе Bitrix"
BITRIX_STATUS_WON = "Договор Bitrix"
BITRIX_STATUS_LOST = "Отказ Bitrix"
BITRIX_STATUS_ARCHIVED = "Архив Bitrix"

NON_REALIZED_STATUSES = (
    "Не позвонили",
    "Перезвонить",
    "Недозвон",
    "Встреча",
    BITRIX_STATUS_IN_PROGRESS,
)

REALIZED_STATUSES = (
    "Договор",
    "Отказ",
    "Архив",
    BITRIX_STATUS_WON,
    BITRIX_STATUS_LOST,
    BITRIX_STATUS_ARCHIVED,
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
