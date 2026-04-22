from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError

from app.dependencies import (
    get_assignment_service,
    get_bitrix_lead_sync_service,
    get_bitrix_placement_service,
    get_settings_dependency,
    require_bitrix_enabled,
)
from app.exceptions import AssignmentConflictError, BitrixSyncConfigurationError, MappingNotFoundError
from app.schemas.assignment import AssignmentBatchResponse, AssignmentConflictResponse
from app.schemas.bitrix import (
    BitrixExecutionContext,
    BitrixInstallPayload,
    BitrixInstallResponse,
    BitrixToolbarRunRequest,
    BitrixToolbarRunResponse,
)
from app.services.assignment_service import AssignmentService
from app.services.bitrix_lead_sync import BitrixLeadSyncService
from app.services.bitrix_placement import BitrixPlacementService

api_router = APIRouter(
    prefix="/bitrix",
    tags=["bitrix"],
    dependencies=[Depends(require_bitrix_enabled)],
)
ui_router = APIRouter(tags=["bitrix-ui"])


async def _parse_install_payload(request: Request) -> BitrixInstallPayload:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        raw = await request.json()
    else:
        form = await request.form()
        raw = dict(form)

    normalized = {
        "portal_domain": raw.get("portal_domain") or raw.get("DOMAIN") or raw.get("domain"),
        "access_token": raw.get("access_token") or raw.get("AUTH_ID") or raw.get("auth_id"),
        "refresh_token": raw.get("refresh_token") or raw.get("REFRESH_ID") or raw.get("refresh_id"),
        "member_id": raw.get("member_id") or raw.get("memberId") or raw.get("member"),
    }
    return BitrixInstallPayload.model_validate(normalized)


@api_router.post("/install", response_model=BitrixInstallResponse)
async def install_bitrix_app(
    request: Request,
    service: BitrixPlacementService = Depends(get_bitrix_placement_service),
):
    try:
        payload = await _parse_install_payload(request)
        return BitrixInstallResponse.model_validate(await service.install(payload))
    except BitrixSyncConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@api_router.post("/uninstall", response_model=BitrixInstallResponse)
async def uninstall_bitrix_app(
    request: Request,
    service: BitrixPlacementService = Depends(get_bitrix_placement_service),
):
    try:
        payload = await _parse_install_payload(request)
        return BitrixInstallResponse.model_validate(await service.uninstall(payload))
    except BitrixSyncConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@api_router.post(
    "/lead-toolbar/run",
    response_model=BitrixToolbarRunResponse,
    responses={409: {"model": AssignmentConflictResponse}},
)
async def run_bitrix_toolbar_flow(
    payload: BitrixToolbarRunRequest,
    assignment_service: AssignmentService = Depends(get_assignment_service),
    sync_service: BitrixLeadSyncService = Depends(get_bitrix_lead_sync_service),
):
    context = BitrixExecutionContext(
        portal_domain=payload.portal_domain,
        access_token=payload.access_token,
        refresh_token=payload.refresh_token,
        member_id=payload.member_id,
        placement=payload.placement,
    )

    try:
        batch = await assignment_service.take_assignments(
            bitrix_user_id=payload.bitrix_user_id,
            dry_run=payload.dry_run,
            bitrix_context=context,
            expect_sync=not payload.dry_run,
        )
        if not payload.dry_run and batch.assigned_count > 0:
            batch = await sync_service.sync_batch(batch.id, context)
        return BitrixToolbarRunResponse(batch=AssignmentBatchResponse.model_validate(batch))
    except MappingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BitrixSyncConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AssignmentConflictError as exc:
        response = AssignmentConflictResponse(
            message=exc.message,
            batch=AssignmentBatchResponse.model_validate(exc.batch),
        )
        return JSONResponse(status_code=409, content=jsonable_encoder(response))


@ui_router.get("/bitrix/toolbar", response_class=HTMLResponse)
async def bitrix_toolbar_page(settings=Depends(get_settings_dependency)) -> HTMLResponse:
    html = f"""
    <!doctype html>
    <html lang="ru">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Vitrina Bitrix</title>
        <script src="https://api.bitrix24.com/api/v1/"></script>
        <style>
          body {{
            font-family: 'Segoe UI', sans-serif;
            margin: 0;
            background: linear-gradient(135deg, #f4efe1, #dfe9dd);
            color: #1e3027;
          }}
          main {{
            max-width: 720px;
            margin: 32px auto;
            background: rgba(255, 255, 255, 0.88);
            border-radius: 20px;
            padding: 24px;
            box-shadow: 0 20px 60px rgba(30, 48, 39, 0.12);
          }}
          button {{
            border: 0;
            border-radius: 999px;
            padding: 12px 18px;
            font-size: 15px;
            cursor: pointer;
            background: #1e6b45;
            color: white;
            margin-right: 12px;
          }}
          pre {{
            white-space: pre-wrap;
            background: #f6f8f4;
            padding: 16px;
            border-radius: 14px;
          }}
        </style>
      </head>
      <body>
        <main>
          <h1>Добавить 10 объектов</h1>
          <p>Кнопка выполняет preview или реальную выдачу и, если нужно, сразу создает лиды в Bitrix.</p>
          <p id="user"></p>
          <div>
            <button type="button" onclick="runFlow(true)">Preview</button>
            <button type="button" onclick="runFlow(false)">Запустить</button>
          </div>
          <pre id="result">Ожидание Bitrix context...</pre>
        </main>
        <script>
          const resultNode = document.getElementById('result');
          const userNode = document.getElementById('user');

          function setResult(value) {{
            resultNode.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
          }}

          function getContext() {{
            const auth = window.BX24 ? BX24.getAuth() : {{}};
            return {{
              bitrix_user_id: String(auth.user_id || auth.member_id || ''),
              portal_domain: auth.domain || '{settings.bitrix_portal_domain or ""}',
              access_token: auth.access_token || auth.AUTH_ID || '',
              refresh_token: auth.refresh_token || auth.REFRESH_ID || '',
              member_id: auth.member_id || '',
              placement: auth.placement || 'CRM_LEAD_LIST_TOOLBAR',
            }};
          }}

          async function runFlow(dryRun) {{
            const context = getContext();
            if (!context.bitrix_user_id) {{
              setResult('Не удалось определить текущего Bitrix пользователя.');
              return;
            }}

            setResult('Выполняется запрос...');
            const response = await fetch('/api/v1/bitrix/lead-toolbar/run', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify({{ ...context, dry_run: dryRun }}),
            }});
            const payload = await response.json();
            setResult(payload);
          }}

          if (window.BX24) {{
            BX24.init(function () {{
              const context = getContext();
              userNode.textContent = context.bitrix_user_id
                ? 'Bitrix user: ' + context.bitrix_user_id
                : 'Bitrix user is not available';
              setResult(context);
            }});
          }} else {{
            setResult('BX24 SDK не загрузился.');
          }}
        </script>
      </body>
    </html>
    """
    return HTMLResponse(html)
