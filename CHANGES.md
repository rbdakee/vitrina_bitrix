# CHANGES

## Статус на 2026-04-22

Репозиторий `vitrina_bitrix` больше не пустой: в нем собран новый backend на `FastAPI`, который использует существующие таблицы `parsed_properties` и `vitrina_agents` только на чтение/обновление бизнес-данных, не меняя их схему. Новые сущности сервиса вынесены в отдельные таблицы и отдельную Alembic migration.

Текущее состояние можно считать как:

- `Phase 1 backend`: реализован в основном объеме.
- `Bitrix Phase 2`: реализован частично, кодовый контур уже есть, но end-to-end проверка и часть тестов еще впереди.
- `Testing Plan`: закрыт частично.

## Что выполнено из `IMPLEMENTATION_PLAN.md`

### Delivery Order: статус по пунктам

| # | Пункт плана | Статус | Комментарий |
|---|---|---|---|
| 1 | Создать каркас проекта и базовую конфигурацию | Done | Созданы `app/`, `migrations/`, `tests/`, `pyproject.toml`, `.env.example`, `alembic.ini`. |
| 2 | Подключить async DB и validation старой схемы | Done | Есть async SQLAlchemy runtime, session factory и startup-валидация legacy-таблиц и обязательных колонок. |
| 3 | Добавить миграции только для новых таблиц | Done | Добавлена Alembic migration `migrations/versions/0001_create_service_tables.py`. |
| 4 | Реализовать repository слой для чтения `parsed_properties` и записи batch-таблиц | Done | Есть repositories для legacy agents, parsed properties, batches и mappings. |
| 5 | Реализовать `AssignmentService` с полным паритетом старой логики | Done | Базовая логика выдачи `10` объектов перенесена и работает через новый service layer. |
| 6 | Реализовать filters API на основе `vitrina_agents.property_classes` | Done | Есть чтение, обновление и очистка фильтров. |
| 7 | Реализовать `LeadPayloadBuilder` | Done | Есть snapshot builder и стабильный Bitrix-ready payload builder. |
| 8 | Реализовать admin API для `bitrix_agent_mappings` | Done | CRUD endpoints и service/repository слой на месте. |
| 9 | Закрыть unit и API тесты Phase 1 | Partial | Unit-тесты на selector и payload builder есть, но API tests и repository/integration tests пока не закрыты. |
| 10 | Реализовать Bitrix local app flow и toolbar integration | Partial | Есть install/uninstall endpoints, toolbar orchestration endpoint и встроенная UI-страница `/bitrix/toolbar`, но живой install flow в реальном Bitrix еще не верифицирован. |
| 11 | Реализовать live lead sync и тесты Phase 2 | Partial | `BitrixLeadSyncService` и transport-layer есть, но нет Phase 2 тестов и live проверки на реальном портале. |

### Что именно уже реализовано

#### 1. Базовая архитектура сервиса

Созданы и заполнены основные каталоги и модули:

- `app/main.py`
- `app/config.py`
- `app/db/session.py`
- `app/db/models.py`
- `app/db/legacy_tables.py`
- `app/db/validators.py`
- `app/repositories/`
- `app/services/`
- `app/api/routes/`
- `app/schemas/`
- `app/bitrix/`
- `migrations/`
- `tests/`

Есть фабрика приложения `create_app()`, настройка логирования, lifespan startup/shutdown и чтение конфигурации из `.env`.

#### 2. Startup и работа с БД

Реализовано:

- чтение `.env` через `pydantic-settings`;
- сборка `DATABASE_URL` из одной строки или из отдельных `DB_*` переменных;
- async engine + `async_sessionmaker`;
- startup validation существующих таблиц:
  - `parsed_properties`
  - `vitrina_agents`
- проверка обязательных колонок для старой схемы;
- отсутствие `ALTER`/`CREATE` для legacy-таблиц на startup.

Важно:

- ограничение из плана соблюдено: старые таблицы не меняются миграциями текущего сервиса;
- новые миграции касаются только новых таблиц текущего backend.

#### 3. Новые таблицы сервиса

Добавлены модели и миграция для:

- `bitrix_agent_mappings`
- `assignment_batches`
- `assignment_batch_items`

Что уже зафиксировано:

- `bitrix_user_id` уникален;
- `assignment_batches.id` хранится как UUID;
- `assignment_batch_items` содержит:
  - `raw_object_snapshot`
  - `lead_payload`
  - `bitrix_lead_id`
  - `sync_status`
  - `sync_error`
- unique constraint на `(batch_id, vitrina_id)` присутствует;
- индексы на ключевые поля batch/items добавлены.

Замечание:

- правило “`agent_phone` должен ссылаться на существующий `vitrina_agents.agent_phone`” сейчас обеспечивается на уровне service validation, а не через DB foreign key, чтобы не связывать новые таблицы жестким FK со старой схемой без отдельного согласования.

#### 4. Business logic выдачи "Добавить 10 объектов"

Перенесено в новый backend:

- источник объектов: только `parsed_properties`;
- eligibility:
  - `krisha_id IS NOT NULL`
  - `krisha_id != ''`
  - `stats_agent_given IS NULL`
- порядок выбора:
  - `ORDER BY krisha_date DESC NULLS LAST, vitrina_id DESC`
- конкурентная семантика:
  - используется `FOR UPDATE SKIP LOCKED` при реальной выдаче;
- базовое распределение:
  - `3 x A`
  - `3 x B`
  - `4 x C`
- fallback:
  - недобор `A` уходит в `B`
  - недобор `B` уходит в `C`
  - `C` включает и `stats_object_category = 'C'`, и `NULL`
- фильтр по классам:
  - сначала поиск по `vitrina_agents.property_classes`
  - затем top-up без фильтра
- лимит `15+` нереализованных объектов:
  - блокирует новую выдачу;
- при `dry_run=false` запись в `parsed_properties` выставляет:
  - `stats_agent_given = agent_phone`
  - `stats_time_given = NOW() AT TIME ZONE 'Asia/Almaty'`
  - `stats_object_status = 'Не позвонили'`
  - `updated_at = NOW()`

#### 5. Assignment batches и service semantics

Реализованы фиксированные статусы:

- `assignment_status`:
  - `preview`
  - `assigned`
  - `blocked_limit`
  - `empty_supply`
  - `failed`
- `sync_status`:
  - `not_requested`
  - `pending`
  - `success`
  - `partial_failed`
  - `failed`

Реализован `dry_run=true`:

- selection-логика выполняется полностью;
- preview batch сохраняется;
- preview items сохраняются;
- `parsed_properties` не обновляется;
- live lead creation в Bitrix не выполняется.

#### 6. Services

Реализованы следующие сервисы:

- `AgentMappingService`
  - resolve `bitrix_user_id -> agent_phone/full_name`
  - CRUD логика для admin API
- `AssignmentService`
  - лимит `15+`
  - selection/fallback `A/B/C`
  - сохранение batch и items
  - обновление `parsed_properties` при реальной выдаче
- `FilterService`
  - чтение и запись `vitrina_agents.property_classes`
  - очистка в `NULL` при пустом списке
- `LeadPayloadBuilder`
  - нормализованный payload для Bitrix
  - raw object snapshot
- `BitrixPlacementService`
  - install/uninstall placement
- `BitrixLeadSyncService`
  - создание лидов из batch items
  - запись `bitrix_lead_id`, `sync_status`, `sync_error`

#### 7. REST API

Сейчас в проекте есть следующие эндпоинты.

Общие:

- `GET /health`

Assignments:

- `POST /api/v1/assignments/take-10`
- `GET /api/v1/assignments/{batch_id}`

Agents / filters:

- `GET /api/v1/agents/{bitrix_user_id}/filters`
- `PUT /api/v1/agents/{bitrix_user_id}/filters`
- `GET /api/v1/property-classes`

Admin mappings:

- `GET /api/v1/admin/bitrix-agent-mappings`
- `POST /api/v1/admin/bitrix-agent-mappings`
- `PUT /api/v1/admin/bitrix-agent-mappings/{bitrix_user_id}`
- `DELETE /api/v1/admin/bitrix-agent-mappings/{bitrix_user_id}`

Bitrix:

- `POST /api/v1/bitrix/install`
- `POST /api/v1/bitrix/uninstall`
- `POST /api/v1/bitrix/lead-toolbar/run`
- `GET /bitrix/toolbar`

#### 8. Bitrix integration

Что уже есть:

- отдельный transport-layer `app/bitrix/client.py`;
- bind/unbind placement через `placement.bind` и `placement.unbind`;
- orchestration endpoint для toolbar flow;
- minimal embedded UI page `/bitrix/toolbar`;
- получение Bitrix context из `BX24.getAuth()`;
- возможность выполнить:
  - preview
  - реальную выдачу
  - live lead sync при наличии токена и portal domain.

Что важно понимать про текущее состояние:

- это кодовый контур Phase 2, а не завершенная production-интеграция;
- реальная привязка local app к конкретному Bitrix-порталу еще не задокументирована и не верифицирована end-to-end;
- UI сейчас минимальная и служит скорее как техническая встроенная страница, чем как финальный polished интерфейс.

#### 9. Lead payload и snapshots

Сейчас payload builder формирует:

- стабильный `title`
- `assignedById`
- `sourceId`
- `sourceDescription`
- `comments`
- `originatorId`
- `originId`
- структуру с телефонами:
  - `phones`
  - `fm`

В `raw_object_snapshot` сохраняется полезный срез полей из `parsed_properties`, перечисленный в `app/constants.py` как `SNAPSHOT_FIELDS`.

#### 10. Тесты и текущая верификация

Сейчас в репозитории есть unit tests:

- `tests/test_assignment_selector.py`
  - точное распределение `3/3/4`
  - перераспределение недобора `A -> B -> C`
  - сначала фильтр по `property_classes`, затем top-up без фильтра
- `tests/test_lead_payload_builder.py`
  - стабильный `title`
  - нормализация телефонов
  - базовая форма payload/snapshot

Последний локально подтвержденный статус:

- `python -m pytest -q`
- результат: `4 passed`

## Что есть в репозитории прямо сейчас

### Конфигурация и запуск

Есть:

- `.env.example`
- `pyproject.toml`
- `alembic.ini`

В `.env.example` уже добавлены ключевые переменные из плана:

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

### Кодовые слои

Слои сейчас разделены так:

- `config` и app bootstrap
- `db`
- `repositories`
- `services`
- `schemas`
- `api/routes`
- `bitrix transport`
- `alembic migrations`
- `tests`

### Текущее ограничение документации

На текущий момент в репозитории еще нет отдельного runbook-а с пошаговым запуском:

- как поднять сервис локально;
- как прогнать Alembic migration на реальной БД;
- как проверить install flow в Bitrix;
- как руками создать первый mapping и сделать первый dry run.

Это не блокирует кодовую базу, но это полезный следующий слой документации.

## Что осталось впереди

### 1. Довести тестовое покрытие до уровня плана

Пока не закрыты следующие группы тестов:

- repository/service tests:
  - параллельные запросы и недопущение повторной выдачи одного `vitrina_id`
  - проверка, что `dry_run` не обновляет `parsed_properties`
  - проверка, что `dry_run` сохраняет preview batch
  - проверка очистки фильтров в `NULL`
- API tests:
  - `unknown bitrix_user_id`
  - `empty supply`
  - `blocked limit`
  - partial batch
  - `GET batch` с persisted snapshots
  - CRUD admin mappings
- Bitrix integration tests:
  - install flow
  - toolbar endpoint
  - сохранение lead IDs
  - partial failure behavior

### 2. Проверить код на реальной PostgreSQL БД

Нужно отдельно пройти реальный smoke/e2e путь:

- применить Alembic migration;
- убедиться, что startup validation проходит на живой БД;
- создать тестовый mapping;
- выполнить `dry_run`;
- выполнить реальную выдачу;
- проверить запись в `assignment_batches`, `assignment_batch_items` и `parsed_properties`.

### 3. Завершить Bitrix Phase 2 до production-ready состояния

Осталось:

- проверить живую регистрацию local app и placement в реальном Bitrix24;
- проверить получение реального текущего пользователя из toolbar placement;
- проверить реальное создание лидов через Bitrix REST;
- убедиться, что частичные ошибки сохраняются корректно на уровне batch/items;
- при необходимости улучшить встроенную UI-страницу до более удобного рабочего состояния.

### 4. Добавить эксплуатационную документацию

Полезно добавить отдельно:

- как запускать проект локально;
- как запускать миграции;
- как наполнять mappings;
- как включать/выключать Bitrix flow через env;
- как прогонять smoke test после деплоя.

## Краткий итог

На данный момент `vitrina_bitrix` уже содержит новый рабочий backend-контур под задачу из `IMPLEMENTATION_PLAN.md`. Основной Phase 1 функционал в коде реализован: есть каркас сервиса, DB слой, новые таблицы, перенос логики выдачи, filters API, admin mappings, batch history и payload builder.

Главные незакрытые области сейчас:

- тестовое покрытие по API/repository/integration;
- реальная проверка на живой PostgreSQL;
- реальная end-to-end проверка Bitrix local app и live lead sync;
- эксплуатационная документация и runbook.
