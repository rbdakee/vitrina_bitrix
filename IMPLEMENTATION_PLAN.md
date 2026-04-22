# IMPLEMENTATION PLAN: `vitrina_bitrix`

## Summary
- Целевой проект для разработки: `~/Desktop/work_projects/vitrina_bitrix`.
- Исходный код, из которого нужно перенести и сохранить текущую бизнес-логику: `~/Desktop/work_projects/agents_crm`.
- Вся разработка идет только в текущем репозитории `vitrina_bitrix`.
- Использовать текущую PostgreSQL БД и существующие таблицы `parsed_properties` и `vitrina_agents` как есть.
- Старые существующие таблицы не менять без отдельного согласования. В этой итерации разрешено создавать только новые таблицы.
- Нужно реализовать один backend на `FastAPI`, который:
  - повторяет текущую логику выдачи "Добавить 10 объектов";
  - работает через REST API;
  - хранит историю batch-выдач;
  - готовит Bitrix-ready payload;
  - затем подключается к Bitrix24 local app и кнопке в `CRM_LEAD_LIST_TOOLBAR`.

## Current Context And Source Of Truth
- В `vitrina_bitrix` сейчас нет кода приложения, только плановые markdown-файлы. Новый проект нужно поднять с нуля.
- Функциональный источник истины находится в `agents_crm` и должен переноситься выборочно, только нужные фрагменты.
- Основные референсы по старому коду:
  - `../agents_crm/handlers.py`
    - `show_bulk_objects_filter_menu`
    - `show_configure_bulk_filter`
    - `handle_clear_property_classes`
    - `handle_add_bulk_objects_confirm`
  - `../agents_crm/database_postgres.py`
    - `assign_latest_parsed_properties`
    - `get_my_objects_status_stats`
    - `get_agent_filter_settings`
    - `save_agent_filter_settings`
    - `clear_agent_filter_settings`
    - `get_distinct_property_classes`
    - `get_my_new_parsed_properties`
  - `../agents_crm/database_schema.sql`
    - схема `parsed_properties`
    - схема `vitrina_agents`
  - `../agents_crm/config.py`
    - паттерн загрузки `DATABASE_URL`
    - `PROPERTY_CLASSES` как fallback в старом приложении
  - `../agents_crm/main.py`
    - startup-последовательность и проверка схемы

## Non-Negotiable Constraints
- Не переносить Telegram UI и Telegram-specific flow. Переносится только бизнес-логика, фильтры и работа с БД.
- Не менять `parsed_properties` и `vitrina_agents` без отдельного согласования.
- Если во время разработки выяснится, что без изменения старых таблиц нельзя обеспечить нужный функционал, нужно остановиться и отдельно описать:
  - какую именно таблицу нужно менять;
  - какую именно колонку/индекс/constraint нужно добавить или изменить;
  - зачем это нужно;
  - почему новую таблицу недостаточно использовать.
- Вся логика выдачи должна остаться семантически эквивалентной старому приложению.

## Business Logic To Preserve Exactly
- Источник объектов для выдачи: только `parsed_properties`.
- Объект может участвовать в выдаче только если:
  - `krisha_id IS NOT NULL`
  - `krisha_id != ''`
  - `stats_agent_given IS NULL`
- Порядок выбора: `ORDER BY krisha_date DESC NULLS LAST, vitrina_id DESC`.
- Конкурентная семантика: эквивалент `FOR UPDATE SKIP LOCKED`.
- Базовое распределение на batch из 10 объектов:
  - `3 x A`
  - `3 x B`
  - `4 x C`
- Fallback-логика:
  - если не хватает `A`, недостающее количество добавляется в `B`;
  - если затем не хватает `B`, остаток уходит в `C`;
  - для категории `C` нужно учитывать и `stats_object_category = 'C'`, и `stats_object_category IS NULL`.
- Фильтр по классам:
  - если у агента заполнены `vitrina_agents.property_classes`, сначала искать только по этим классам;
  - если объектов не хватает, дозабирать без фильтра по классам;
  - фильтр не должен ломать базовую схему `A/B/C`.
- Лимит перед выдачей:
  - если у агента уже `15` или больше нереализованных объектов, новая выдача запрещена;
  - нереализованными считаются только статусы:
    - `Не позвонили`
    - `Перезвонить`
    - `Недозвон`
    - `Встреча`
  - статусы `Договор`, `Отказ`, `Архив` в этот лимит не входят.
- При успешной выдаче в `parsed_properties` должны записываться те же значения, что и в старом коде:
  - `stats_agent_given = agent_phone`
  - `stats_time_given = NOW() AT TIME ZONE 'Asia/Almaty'`
  - `stats_object_status = 'Не позвонили'`
  - `updated_at = NOW()`

## Target Architecture
- Поднять новый `FastAPI` backend в текущем репозитории со следующей структурой:
  - `app/main.py`
  - `app/config.py`
  - `app/db/session.py`
  - `app/db/models.py`
  - `app/repositories/`
  - `app/services/`
  - `app/api/routes/`
  - `app/schemas/`
  - `app/bitrix/`
  - `migrations/`
  - `tests/`
- Технологическая база:
  - `FastAPI`
  - `SQLAlchemy` async
  - `asyncpg`
  - `Pydantic`
  - `Alembic` только для новых таблиц текущего сервиса
  - `httpx` для Bitrix API
- Startup нового сервиса должен:
  - читать `.env`;
  - поднимать async DB engine/session;
  - проверять доступность существующих таблиц `parsed_properties` и `vitrina_agents`;
  - проверять наличие обязательных колонок, от которых зависит логика;
  - не выполнять `ALTER` или `CREATE` для старых таблиц.

## New Tables To Create
- `bitrix_agent_mappings`
  - `id`
  - `bitrix_user_id` unique
  - `agent_phone`
  - `full_name`
  - `created_at`
  - `updated_at`
- Правила для `bitrix_agent_mappings`:
  - `agent_phone` должен ссылаться на существующий `vitrina_agents.agent_phone`;
  - `full_name` хранить как snapshot для удобства, но источником истины по агенту остается `vitrina_agents`.
- `assignment_batches`
  - `id` UUID
  - `bitrix_user_id`
  - `agent_phone`
  - `portal_domain` nullable
  - `requested_count`
  - `assigned_count`
  - `selected_property_classes` JSONB или ARRAY
  - `category_counts` JSONB
  - `assignment_status`
  - `sync_status`
  - `dry_run`
  - `error_message`
  - `created_at`
  - `updated_at`
- `assignment_batch_items`
  - `id`
  - `batch_id`
  - `batch_position`
  - `vitrina_id`
  - `category`
  - `raw_object_snapshot` JSONB
  - `lead_payload` JSONB
  - `bitrix_lead_id` nullable
  - `sync_status`
  - `sync_error`
  - `created_at`
  - `updated_at`
- Обязательные ограничения:
  - unique `(batch_id, vitrina_id)`
  - индексы на `bitrix_user_id`, `agent_phone`, `sync_status`, `created_at`

## Fixed Statuses And Service Semantics
- `assignment_status` зафиксировать:
  - `preview`
  - `assigned`
  - `blocked_limit`
  - `empty_supply`
  - `failed`
- `sync_status` зафиксировать:
  - `not_requested`
  - `pending`
  - `success`
  - `partial_failed`
  - `failed`
- `dry_run=true` должен:
  - отработать всю selection-логику;
  - сформировать preview batch и preview items;
  - не обновлять `parsed_properties`;
  - не создавать лиды в Bitrix.

## Services To Implement
- `AgentMappingService`
  - resolve `bitrix_user_id -> agent_phone/full_name`
  - CRUD для mappings через admin API
- `AssignmentService`
  - реализует лимит 15+
  - реализует selection и fallback `A/B/C`
  - сохраняет batch и items
  - при `dry_run=false` обновляет `parsed_properties`
- `FilterService`
  - читает и пишет `vitrina_agents.property_classes`
  - пустой набор фильтров должен очищать значение в `NULL`
- `LeadPayloadBuilder`
  - строит стабильный payload для будущего Bitrix lead creation
  - сохраняет полный raw snapshot объекта
- `BitrixPlacementService`
  - install/uninstall placement
  - orchestration вызова из Bitrix local app
- `BitrixLeadSyncService`
  - создает лиды по batch items
  - пишет `bitrix_lead_id`, `sync_status`, `sync_error`

## REST API Contract
- `POST /api/v1/assignments/take-10`
  - input:
    - `bitrix_user_id`
    - optional `dry_run`
  - behavior:
    - resolve mapping;
    - проверить лимит;
    - выполнить выдачу или preview;
    - сохранить batch;
    - вернуть batch summary, список объектов и payload preview.
- `GET /api/v1/assignments/{batch_id}`
  - вернуть batch header, category split, item list, sync status, lead IDs/errors.
- `GET /api/v1/agents/{bitrix_user_id}/filters`
  - найти mapping;
  - вернуть текущий `property_classes`.
- `PUT /api/v1/agents/{bitrix_user_id}/filters`
  - input: список классов;
  - записать их в `vitrina_agents.property_classes`;
  - пустой список трактовать как очистку фильтра.
- `GET /api/v1/property-classes`
  - вернуть `SELECT DISTINCT property_class FROM parsed_properties WHERE property_class IS NOT NULL ORDER BY property_class`.

## Admin API For Mapping Management
- Нужен отдельный закрытый admin API, потому что готового источника `bitrix_user_id` в старой системе нет.
- Защита: `X-Admin-Token` из `.env`.
- Эндпоинты:
  - `GET /api/v1/admin/bitrix-agent-mappings`
  - `POST /api/v1/admin/bitrix-agent-mappings`
  - `PUT /api/v1/admin/bitrix-agent-mappings/{bitrix_user_id}`
  - `DELETE /api/v1/admin/bitrix-agent-mappings/{bitrix_user_id}`
- Правила:
  - нельзя создать mapping на несуществующий `agent_phone`;
  - при создании по умолчанию подтягивать `full_name` из `vitrina_agents`, если он там есть;
  - `bitrix_user_id` должен быть уникальным.

## Bitrix Integration Scope
- Phase 1:
  - backend, API, mappings, filters, batch history, payload preview;
  - без live записи в Bitrix.
- Phase 2:
  - подключить Bitrix24 local app;
  - зарегистрировать кнопку в `CRM_LEAD_LIST_TOOLBAR`;
  - открыть встроенную UI-страницу приложения;
  - получить текущего Bitrix пользователя;
  - вызвать backend orchestration endpoint;
  - создать лиды в Bitrix;
  - сохранить результат синка в batch/items.

## Bitrix Phase 2 Contract
- Добавить install endpoint для local app.
- Во время install регистрировать placement для `CRM_LEAD_LIST_TOOLBAR`.
- Добавить UI endpoint/page для открытия внутри Bitrix.
- UI должна:
  - определить текущего Bitrix пользователя;
  - показать короткий preview результата;
  - запустить выдачу и синк;
  - показать итог: сколько объектов взято и сколько лидов создано.
- Добавить orchestration endpoint:
  - `POST /api/v1/bitrix/lead-toolbar/run`
  - input:
    - `bitrix_user_id`
    - optional `dry_run`
    - optional portal metadata
  - behavior:
    - выполнить `AssignmentService`;
    - если не `dry_run`, вызвать `BitrixLeadSyncService`.
- Создание лидов делать через Bitrix REST с отдельным adapter/service слоем, не смешивать Bitrix transport с assignment-логикой.

## Lead Payload Rules
- В `assignment_batch_items.lead_payload` сохранять нормализованный payload.
- Минимальные стабильные поля:
  - `title`
  - `assignedById`
  - `sourceId`
  - `sourceDescription`
  - `comments`
  - `originatorId`
  - `originId`
  - `fm` или эквивалентная структура с телефонами
- В `raw_object_snapshot` сохранять все полезные поля объекта из `parsed_properties`, используемые в старом `get_my_new_parsed_properties`, включая:
  - `vitrina_id`
  - `rbd_id`
  - `krisha_id`
  - `krisha_date`
  - `object_type`
  - `address`
  - `complex`
  - `builder`
  - `flat_type`
  - `property_class`
  - `condition`
  - `sell_price`
  - `sell_price_per_m2`
  - `house_num`
  - `floor_num`
  - `floor_count`
  - `room_count`
  - `phones`
  - `description`
  - `ceiling_height`
  - `area`
  - `year_built`
  - `wall_type`
  - `stats_object_status`
  - `stats_description`
- Title по умолчанию строить стабильно и детерминированно:
  - `"[Vitrina] {object_type or 'Объект'} | {address or 'Без адреса'} | ID {vitrina_id}"`

## Error Handling Rules
- Если mapping не найден:
  - `404`
  - без попытки selection
- Если лимит 15+ превышен:
  - `409`
  - batch сохраняется со статусом `blocked_limit`
- Если свободных объектов нет:
  - `409`
  - batch сохраняется со статусом `empty_supply`
- Если Bitrix sync частично провалился:
  - batch получает `partial_failed`
  - item-level ошибки сохраняются отдельно

## Configuration
- `.env.example` должен включать:
  - `DATABASE_URL`
  - `APP_ENV`
  - `APP_HOST`
  - `APP_PORT`
  - `LOG_LEVEL`
  - `ADMIN_API_TOKEN`
  - `BITRIX_ENABLED`
  - `BITRIX_PORTAL_DOMAIN`
  - `BITRIX_APP_CLIENT_ID`
  - `BITRIX_APP_CLIENT_SECRET`
  - `BITRIX_APP_PUBLIC_BASE_URL`
  - `BITRIX_LEAD_STAGE_ID`
  - `BITRIX_LEAD_CATEGORY_ID`
- Конфиг должен позволять отключать Bitrix flow, сохраняя рабочий Phase 1 backend.

## Testing Plan
- Unit tests:
  - лимит `15+` блокирует выдачу;
  - точное распределение `3/3/4`;
  - недобор `A` перераспределяется в `B`;
  - недобор `B` перераспределяется в `C`;
  - категория `C` включает `NULL`;
  - сначала фильтр по `property_classes`, затем top-up без фильтра;
  - deterministic ordering по `krisha_date DESC NULLS LAST, vitrina_id DESC`.
- Repository/service tests:
  - параллельные запросы не получают одинаковый `vitrina_id`;
  - `dry_run` не обновляет `parsed_properties`;
  - `dry_run` все равно сохраняет preview batch;
  - очистка фильтров ставит `property_classes = NULL`.
- API tests:
  - unknown `bitrix_user_id`;
  - empty supply;
  - blocked limit;
  - partial batch, если в supply меньше 10 объектов;
  - GET batch возвращает persisted snapshots;
  - CRUD mappings через admin API.
- Bitrix integration tests:
  - install flow регистрирует placement;
  - toolbar endpoint получает пользователя;
  - успешные lead IDs сохраняются в items;
  - частичная ошибка Bitrix не ломает уже созданные лиды.

## Delivery Order
1. Создать каркас проекта и базовую конфигурацию.
2. Подключить async DB и validation старой схемы.
3. Добавить миграции только для новых таблиц.
4. Реализовать repository слой для чтения `parsed_properties` и записи batch-таблиц.
5. Реализовать `AssignmentService` с полным паритетом старой логики.
6. Реализовать filters API на основе `vitrina_agents.property_classes`.
7. Реализовать `LeadPayloadBuilder`.
8. Реализовать admin API для `bitrix_agent_mappings`.
9. Закрыть unit и API тесты Phase 1.
10. Реализовать Bitrix local app flow и toolbar integration.
11. Реализовать live lead sync и тесты Phase 2.

## Final Assumptions
- Единственный актуальный проект разработки: `vitrina_bitrix`.
- Старый `agents_crm` используется только как reference.
- Отдельный второй репозиторий для этого функционала не используется.
- Старые планы больше не актуальны; этот файл является единственным источником контекста для следующей сессии разработки.
