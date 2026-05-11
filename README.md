# vitrina-bitrix

Backend-сервис, который выдаёт агентам холодные объекты из базы Vitrina и автоматически создаёт по ним сделки в Bitrix24.

## Что делает

- Агент заходит в **CRM → Сделки** в Bitrix24 и нажимает кнопку **«Добавить 10 объектов»** на тулбаре.
- Backend выбирает 10 свободных объектов из `parsed_properties` с учётом квот A/B/C (3/3/4) и `property_class` агента, помечает их назначенными (`stats_agent_given`).
- На каждый объект создаётся **контакт** (с телефонами продавца) и **сделка** в воронке "Предложение (продажа/аренда)" → стадия "Лид", с UF-полями: тип недвижимости, площадь, этаж/этажность, год постройки, комнатность, цена, состояние, адрес, ссылка на ЖК (smart-процесс 1072).
- Имя ЖК сматчивается со смарт-процессом ЖК через ленивый persistent-кеш (`var/complex_cache.json`). Если матч не найден — название кладётся в комменты.
- В комменты сделки также пишутся: krisha.kz ссылка, застройщик, класс объекта, цена за м², высота потолков, материал стен, описание и т.д.
- У агента действует лимит: если у него уже **15 и больше** нереализованных объектов (статусы "Не позвонили", "Перезвонить", "Недозвон", "Встреча"), новая выдача блокируется.

## Стек

- Python 3.11+ / FastAPI / SQLAlchemy 2 (async) / asyncpg / Alembic
- Postgres (внешняя БД, не управляется этим сервисом)
- Bitrix24 local server-side application (OAuth + placement bind)

## Структура

```
app/
  api/routes/         FastAPI endpoints (admin, bitrix install/uninstall, deal-toolbar, health, UI)
  bitrix/client.py    Bitrix REST client (call_method, create_contact, create_deal_with_contact, placement bind/unbind)
  services/           Бизнес-логика
    assignment_service.py    Выбор 10 объектов, проверка лимита, формирование payload
    deal_payload.py          Маппинг snapshot → payload сделки + комменты
    bitrix_deal_sync.py      Создание контакта и сделки на каждый item
    bitrix_placement.py      install/uninstall placement в Bitrix
    complex_matcher.py       Ленивый persistent-кеш ЖК со страничной подгрузкой
    selection.py             Алгоритм выбора A/B/C
    agent_mapping_service.py bitrix_user_id → agent_phone
    filter_service.py        Фильтры property_class агента
  repositories/       SQLAlchemy Core запросы к parsed_properties + служебным таблицам
  db/                 Сессия, валидаторы legacy-схемы
  config.py           Settings (pydantic-settings + .env)
  constants.py        Лимиты, UF-коды, enum-маппинги, source/stage ID
  schemas/            Pydantic-модели запросов/ответов
migrations/           Alembic (служебные таблицы: assignment_batches, assignment_batch_items, bitrix_agent_mappings)
var/                  Runtime data (complex_cache.json) — не коммитится
```

## Локальный запуск (без Docker)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env   # затем заполнить
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Запуск в Docker

См. **DEPLOY.md**.

## Bitrix-приложение

Local server-side app:
- **Handler URL установки**: `https://<BITRIX_APP_PUBLIC_BASE_URL>/api/v1/bitrix/install`
- **Scope**: `crm`, `placement`, `user`
- **Placement**: `CRM_DEAL_LIST_TOOLBAR` — биндится автоматически при установке (handler: `https://<...>/bitrix/toolbar`).

После смены `BITRIX_APP_PUBLIC_BASE_URL` или замены placement в коде — переустановить приложение через "Переустановить" в карточке приложения в Bitrix24.

## Админ-эндпоинты

Защищены заголовком `X-Admin-Token: <ADMIN_API_TOKEN>`. Используются для создания/обновления маппинга `bitrix_user_id → agent_phone` и просмотра батчей.

## Ключевые таблицы (внешняя БД)

- `parsed_properties` — источник объектов (managed elsewhere). Сервис читает поля по списку `app/constants.py:SNAPSHOT_FIELDS` и пишет в неё только `stats_agent_given` (при назначении).
- `assignment_batches`, `assignment_batch_items` — служебные, накатываются Alembic-миграцией `0001_create_service_tables`.
- `bitrix_agent_mappings` — служебная, маппинг bitrix-юзера на phone агента.
