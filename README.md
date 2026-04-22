# vitrina_bitrix

FastAPI backend for Vitrina -> Bitrix assignment flow.

## What is in the repo

- FastAPI app with async SQLAlchemy
- migration for new service tables only
- business logic for "Добавить 10 объектов"
- filters API based on `vitrina_agents.property_classes`
- admin API for Bitrix user -> agent mappings
- Bitrix toolbar/install flow scaffold
- unit tests for selection and payload building

## Project structure

```text
app/
  api/
  bitrix/
  db/
  repositories/
  schemas/
  services/
migrations/
tests/
```

## Requirements

- Python 3.11+
- PostgreSQL with existing legacy tables:
  - `parsed_properties`
  - `vitrina_agents`

## Local setup

1. Create a virtual environment.
2. Install dependencies:

```bash
pip install -e .[dev]
```

3. Create `.env` from `.env.example`.
4. Run migrations for new service tables:

```bash
alembic upgrade head
```

5. Start the API:

```bash
uvicorn app.main:app --reload
```

## Useful commands

Run tests:

```bash
python -m pytest -q
```

Quick syntax sanity check:

```bash
python -m compileall app migrations tests
```

## Main endpoints

- `GET /health`
- `POST /api/v1/assignments/take-10`
- `GET /api/v1/assignments/{batch_id}`
- `GET /api/v1/agents/{bitrix_user_id}/filters`
- `PUT /api/v1/agents/{bitrix_user_id}/filters`
- `GET /api/v1/property-classes`
- `GET/POST/PUT/DELETE /api/v1/admin/bitrix-agent-mappings`
- `POST /api/v1/bitrix/install`
- `POST /api/v1/bitrix/uninstall`
- `POST /api/v1/bitrix/lead-toolbar/run`
- `GET /bitrix/toolbar`

## Notes

- Legacy tables are validated on startup, but not migrated by this service.
- Current implementation status is documented in `CHANGES.md`.
- Source implementation plan is in `IMPLEMENTATION_PLAN.md`.

