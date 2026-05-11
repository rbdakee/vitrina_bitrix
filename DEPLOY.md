# Деплой vitrina-bitrix

## Требования к окружению

- Docker 24+ и Docker Compose v2.
- Стабильный публичный HTTPS-URL (Bitrix24 не принимает HTTP-handler). Если домена ещё нет — поставить **nginx + Let's Encrypt** или Cloudflare Tunnel перед контейнером.
- Доступ к Postgres (внешний — `db-prod.jurta.kz:30101` в текущем `.env`).
- Доступ к порталу Bitrix24 с правами администратора (для переустановки приложения с прод-handler URL).

## 1. Подготовка `.env`

Скопировать пример и заполнить под прод:

```bash
cp .env.example .env
```

Заполнить:

| Переменная | Значение |
|---|---|
| `APP_ENV` | `production` |
| `LOG_LEVEL` | `INFO` (или `WARNING`) |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:port/dbname` — прод-БД |
| `ADMIN_API_TOKEN` | длинный рандом (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `BITRIX_ENABLED` | `true` |
| `BITRIX_PORTAL_DOMAIN` | `vitrina.bitrix24.kz` |
| `BITRIX_APP_CLIENT_ID` / `BITRIX_APP_CLIENT_SECRET` | из карточки приложения в Bitrix |
| `BITRIX_APP_PUBLIC_BASE_URL` | **прод HTTPS-URL** этого сервиса, например `https://vitrina-api.jurta.kz` (без trailing slash) |
| `BITRIX_DEAL_CATEGORY_ID` | `133` |
| `BITRIX_DEAL_STAGE_ID` | `C133:UC_5Q8TR6` |
| `BITRIX_COMPLEX_CACHE_PATH` | `var/complex_cache.json` (по умолчанию) |

## 2. Запуск контейнера

```bash
docker compose up -d --build
docker compose logs -f api
```

Проверка живости:

```bash
curl http://localhost:8000/health
# → {"status":"ok"}
```

Кеш ЖК и runtime-файлы лежат в `./var` (volume) — пережил рестарты контейнера.

## 3. Reverse proxy (пример nginx)

```nginx
server {
    listen 443 ssl http2;
    server_name vitrina-api.jurta.kz;

    ssl_certificate     /etc/letsencrypt/live/vitrina-api.jurta.kz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vitrina-api.jurta.kz/privkey.pem;

    client_max_body_size 2m;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

## 4. Миграции БД

Сервисные таблицы (`assignment_batches`, `assignment_batch_items`, `bitrix_agent_mappings`) уже накатаны на текущей БД. Если деплоим с нуля или появилась новая миграция:

```bash
docker compose exec api alembic upgrade head
```

## 5. Переустановка Bitrix-приложения с прод-URL

В Bitrix24 → Приложения → **Vitrina** (local app) → открыть карточку → нажать **"Переустановить"**. Bitrix сделает POST на `<BITRIX_APP_PUBLIC_BASE_URL>/api/v1/bitrix/install`, сервис привяжет placement `CRM_DEAL_LIST_TOOLBAR` к `<BITRIX_APP_PUBLIC_BASE_URL>/bitrix/toolbar`.

Если приложение раньше указывало на ngrok — старая привязка отвалится, новая встанет. Проверить: открыть **CRM → Сделки**, увидеть кнопку **"Добавить 10 объектов"** над списком.

## 6. Маппинги агентов

Если на проде ещё нет ни одной записи в `bitrix_agent_mappings`, агент не сможет получить выдачу. Создать через админ-эндпоинт:

```bash
curl -X POST https://vitrina-api.jurta.kz/api/v1/admin/bitrix-agent-mappings \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"bitrix_user_id":"22213","agent_phone":"7005545478","full_name":"..."}'
```

## 7. Проверка готовности к прод-нагрузке

1. **Health**: `curl https://vitrina-api.jurta.kz/health` → 200.
2. **OpenAPI**: `https://vitrina-api.jurta.kz/docs` — все эндпоинты доступны.
3. **Установка приложения** в Bitrix → 200 + HTML с installFinish.
4. **Кнопка в CRM → Сделки** появляется, открывает наш слайдер.
5. **Preview** на тестовом агенте — возвращает 10 объектов.
6. **Запустить** — создаёт 10 сделок, в карточке каждой видны UF-поля.

## Что мониторить

- `docker compose logs api` — все ошибки Bitrix REST логируются как `RuntimeError` с error_code из payload.
- Свободное место под `./var` — кеш ЖК ~200 КБ, растёт только при появлении новых ЖК.
- Размер таблицы `assignment_batches` — батч на каждый клик, item'ы внутри. Ротацию можно добавить позже SQL-запросом по `created_at`.

## Обновление кода

```bash
git pull
docker compose up -d --build
# при наличии новых миграций:
docker compose exec api alembic upgrade head
```

`var/complex_cache.json` переживает обновление (volume). Если структура смарт-процесса ЖК поменялась в Bitrix — удалить файл, кеш переподтянется.

## Откат

```bash
git checkout <previous-tag>
docker compose up -d --build
```

Если миграция тоже откатывается:

```bash
docker compose exec api alembic downgrade -1
```
