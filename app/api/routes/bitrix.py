from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.dependencies import (
    get_assignment_service,
    get_bitrix_deal_sync_service,
    get_bitrix_placement_service,
    get_mapping_service,
    get_settings_dependency,
    require_bitrix_enabled,
)
from app.exceptions import AssignmentConflictError, BitrixSyncConfigurationError, MappingNotFoundError
from app.schemas.assignment import AssignmentBatchResponse, AssignmentConflictResponse
from app.schemas.bitrix import (
    BitrixExecutionContext,
    BitrixInstallPayload,
    BitrixInstallResponse,
    BitrixNeedsOnboardingResponse,
    BitrixOnboardRequest,
    BitrixOnboardResponse,
    BitrixToolbarRunRequest,
    BitrixToolbarRunResponse,
)
from app.services.agent_mapping_service import (
    AgentMappingService,
    InvalidPhoneError,
    OnboardingRequiredSignal,
    PhoneAlreadyBoundError,
)
from app.services.assignment_service import AssignmentService
from app.services.bitrix_deal_sync import BitrixDealSyncService
from app.services.bitrix_placement import BitrixPlacementService

logger = logging.getLogger(__name__)

api_router = APIRouter(
    prefix="/bitrix",
    tags=["bitrix"],
    dependencies=[Depends(require_bitrix_enabled)],
)
ui_router = APIRouter(tags=["bitrix-ui"])


async def _parse_install_payload(request: Request) -> BitrixInstallPayload:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        raw = dict(await request.json())
    else:
        form = await request.form()
        raw = dict(form)

    query = dict(request.query_params)

    def pick(*keys):
        for source in (raw, query):
            for key in keys:
                value = source.get(key)
                if value:
                    return value
        return None

    normalized = {
        "portal_domain": pick("portal_domain", "DOMAIN", "domain"),
        "access_token": pick("access_token", "AUTH_ID", "auth_id"),
        "refresh_token": pick("refresh_token", "REFRESH_ID", "refresh_id"),
        "member_id": pick("member_id", "memberId", "member"),
    }
    return BitrixInstallPayload.model_validate(normalized)


_INSTALL_FINISH_HTML = """<!doctype html>
<html lang="ru">
  <head>
    <meta charset="utf-8" />
    <title>Vitrina installed</title>
    <script src="//api.bitrix24.com/api/v1/"></script>
  </head>
  <body>
    <p>Установка завершена.</p>
    <script>
      if (window.BX24) {
        BX24.init(function () { BX24.installFinish(); });
      }
    </script>
  </body>
</html>"""


_TOOLBAR_HTML_TEMPLATE = """<!doctype html>
<html lang="ru">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Vitrina · выдача объектов</title>
    <script src="https://api.bitrix24.com/api/v1/"></script>
    <style>
      :root {
        --bg-1: #f4efe1;
        --bg-2: #dfe9dd;
        --ink: #1e3027;
        --ink-soft: #5a6b62;
        --ink-mute: #8c9a92;
        --line: #e1e7df;
        --card: #ffffff;
        --accent: #1e6b45;
        --accent-soft: #e6f0eb;
        --warn: #b86b1f;
        --warn-soft: #fbeed6;
        --bad: #b03434;
        --bad-soft: #f7dede;
        --ok: #1e8a55;
        --ok-soft: #dff1e6;
        --shadow: 0 10px 40px rgba(30, 48, 39, 0.10);
      }
      * { box-sizing: border-box; }
      body {
        font-family: 'Segoe UI', system-ui, sans-serif;
        margin: 0;
        background: linear-gradient(135deg, var(--bg-1), var(--bg-2));
        color: var(--ink);
        min-height: 100vh;
      }
      main {
        max-width: 760px;
        margin: 24px auto;
        background: rgba(255, 255, 255, 0.92);
        border-radius: 18px;
        padding: 20px 22px;
        box-shadow: var(--shadow);
      }
      header { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
      h1 { margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -0.01em; }
      .user { font-size: 13px; color: var(--ink-mute); }
      .actions { display: flex; gap: 10px; margin: 18px 0 8px; }
      .hints { font-size: 12px; color: var(--ink-soft); margin: 0 0 14px; line-height: 1.5; }
      .hints b { color: var(--ink); font-weight: 600; }
      .hints div + div { margin-top: 4px; }
      button {
        border: 0;
        border-radius: 999px;
        padding: 10px 18px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        background: var(--accent);
        color: white;
        transition: background 0.15s, opacity 0.15s;
      }
      button.secondary {
        background: var(--card);
        color: var(--ink);
        border: 1px solid var(--line);
      }
      button:hover:not(:disabled) { opacity: 0.9; }
      button:disabled { opacity: 0.5; cursor: not-allowed; }
      .banner {
        border-radius: 12px;
        padding: 12px 14px;
        font-size: 14px;
        margin: 12px 0;
        line-height: 1.4;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .banner.ok   { background: var(--ok-soft);   color: var(--ok);   border-left: 3px solid var(--ok); }
      .banner.warn { background: var(--warn-soft); color: var(--warn); border-left: 3px solid var(--warn); }
      .banner.bad  { background: var(--bad-soft);  color: var(--bad);  border-left: 3px solid var(--bad); }
      .banner.info { background: var(--accent-soft); color: var(--accent); border-left: 3px solid var(--accent); }
      .banner strong { font-weight: 600; }
      .summary {
        display: flex; gap: 16px; margin: 8px 0 14px;
        font-size: 13px; color: var(--ink-soft); flex-wrap: wrap;
      }
      .summary b { color: var(--ink); font-weight: 600; }
      .item {
        display: grid;
        grid-template-columns: 28px 1fr auto;
        gap: 10px 12px;
        padding: 12px 0;
        border-bottom: 1px solid var(--line);
        align-items: start;
      }
      .item:last-child { border-bottom: 0; }
      .item .pos { font-size: 13px; color: var(--ink-mute); padding-top: 2px; }
      .item .body .title { font-size: 14px; font-weight: 500; line-height: 1.35; }
      .item .body .meta { font-size: 12px; color: var(--ink-soft); margin-top: 4px; }
      .item .body .sync { font-size: 12px; margin-top: 6px; }
      .item .price { font-size: 14px; font-weight: 600; text-align: right; white-space: nowrap; }
      .badge {
        display: inline-block; padding: 1px 7px; border-radius: 999px;
        font-size: 11px; font-weight: 600; vertical-align: middle;
        margin-right: 6px;
      }
      .badge.A { background: #e6f0eb; color: #1e6b45; }
      .badge.B { background: #fbeed6; color: #b86b1f; }
      .badge.C { background: #e8e8ef; color: #5a5a78; }
      .sync.ok { color: var(--ok); }
      .sync.bad { color: var(--bad); }
      .sync.mute { color: var(--ink-mute); }
      a { color: var(--accent); text-decoration: none; }
      a:hover { text-decoration: underline; }
      .empty { color: var(--ink-mute); font-size: 14px; padding: 8px 0; }
      .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid var(--accent-soft); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; }
      @keyframes spin { to { transform: rotate(360deg); } }
      .onboard { padding: 8px 0 4px; }
      .onboard-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
      .onboard-desc { font-size: 13px; color: var(--ink-soft); line-height: 1.45; margin-bottom: 12px; }
      .onboard-fio { font-size: 13px; color: var(--ink); margin-bottom: 14px; }
      .onboard-fio .mute { color: var(--ink-mute); }
      .onboard-row { display: flex; gap: 8px; align-items: stretch; flex-wrap: wrap; }
      .onboard-input { flex: 1; min-width: 220px; padding: 10px 14px; border: 1px solid var(--line); border-radius: 999px; font-size: 14px; font-family: inherit; }
      .onboard-input:focus { outline: 2px solid var(--accent-soft); outline-offset: 0; border-color: var(--accent); }
      .onboard-submit { padding: 10px 18px; border-radius: 999px; border: 0; background: var(--accent); color: white; font-size: 14px; cursor: pointer; }
      .onboard-submit:disabled { opacity: 0.5; cursor: not-allowed; }
      .onboard-error { color: var(--bad); font-size: 13px; margin-top: 8px; min-height: 18px; }
    </style>
  </head>
  <body>
    <main>
      <header>
        <h1>Vitrina · выдача 10 объектов</h1>
        <div class="user" id="user">Загрузка пользователя...</div>
      </header>

      <div class="actions">
        <button type="button" id="btn-preview" class="secondary">Предпросмотр</button>
        <button type="button" id="btn-run">Запустить выдачу</button>
      </div>
      <div class="hints">
        <div><b>Предпросмотр</b> — показывает какие 10 объектов вам выпадут, без создания сделок в Bitrix.</div>
        <div><b>Запустить выдачу</b> — создаёт 10 сделок в Bitrix и закрепляет объекты за вами.</div>
      </div>

      <div id="status"></div>
      <div id="items"></div>
    </main>

    <script>
      const PORTAL_DOMAIN_DEFAULT = '__PORTAL_DOMAIN__';

      const statusNode = document.getElementById('status');
      const itemsNode = document.getElementById('items');
      const userNode = document.getElementById('user');
      const btnPreview = document.getElementById('btn-preview');
      const btnRun = document.getElementById('btn-run');

      let currentUser = null;

      function el(tag, attrs, children) {
        const node = document.createElement(tag);
        if (attrs) {
          for (const k in attrs) {
            if (k === 'class') node.className = attrs[k];
            else if (k === 'text') node.textContent = attrs[k];
            else if (k === 'href') node.setAttribute('href', attrs[k]);
            else if (k === 'target') node.setAttribute('target', attrs[k]);
            else if (k === 'rel') node.setAttribute('rel', attrs[k]);
            else node.setAttribute(k, attrs[k]);
          }
        }
        if (children) {
          for (const child of children) {
            if (child === null || child === undefined || child === false) continue;
            node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
          }
        }
        return node;
      }

      function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

      function formatPrice(value) {
        if (value === null || value === undefined || value === '') return '';
        const num = Number(value);
        if (!isFinite(num)) return '';
        return num.toLocaleString('ru-RU').replace(/,/g, ' ') + ' ₸';
      }

      function showBanner(kind, parts) {
        clear(statusNode);
        const banner = el('div', { class: 'banner ' + kind });
        if (typeof parts === 'string') {
          banner.appendChild(document.createTextNode(parts));
        } else {
          for (const p of parts) banner.appendChild(typeof p === 'string' ? document.createTextNode(p) : p);
        }
        statusNode.appendChild(banner);
      }

      function getAuth() { return window.BX24 ? BX24.getAuth() : {}; }

      function buildContext() {
        const auth = getAuth();
        const profile = currentUser ? {
          name: currentUser.NAME || null,
          last_name: currentUser.LAST_NAME || null,
          second_name: currentUser.SECOND_NAME || null,
          work_phone: currentUser.WORK_PHONE || null,
          personal_mobile: currentUser.PERSONAL_MOBILE || null,
        } : null;
        return {
          bitrix_user_id: String((currentUser && currentUser.ID) || ''),
          portal_domain: auth.domain || PORTAL_DOMAIN_DEFAULT,
          access_token: auth.access_token || auth.AUTH_ID || '',
          refresh_token: auth.refresh_token || auth.REFRESH_ID || '',
          member_id: auth.member_id || '',
          placement: 'CRM_DEAL_LIST_TOOLBAR',
          profile: profile,
        };
      }

      function renderSummary(batch) {
        const counts = batch.category_counts || { A: 0, B: 0, C: 0 };
        const wrap = el('div', { class: 'summary' });
        const cat = el('span', null, [
          'Категории: ',
          el('b', { text: 'A=' + (counts.A || 0) }), ' · ',
          el('b', { text: 'B=' + (counts.B || 0) }), ' · ',
          el('b', { text: 'C=' + (counts.C || 0) }),
        ]);
        wrap.appendChild(cat);
        if (batch.agent_phone) {
          wrap.appendChild(el('span', null, ['Агент: ', el('b', { text: batch.agent_phone })]));
        }
        return wrap;
      }

      function renderItem(it, dryRun) {
        const snap = it.raw_object_snapshot || {};
        const title = snap.complex || snap.address || ('Объект ' + snap.vitrina_id);
        const subtitle = snap.complex ? (snap.address || '') : '';
        const metaParts = [];
        if (snap.room_count) metaParts.push(snap.room_count + '-комн');
        if (snap.area) metaParts.push(snap.area + ' м²');
        if (snap.floor_num && snap.floor_count) metaParts.push(snap.floor_num + '/' + snap.floor_count + ' эт');
        else if (snap.floor_num) metaParts.push(snap.floor_num + ' эт');
        if (snap.year_built) metaParts.push(snap.year_built + ' г.');

        const category = it.category || 'C';
        const titleRow = el('div', { class: 'title' }, [
          el('span', { class: 'badge ' + category, text: it.category || '?' }),
          title,
        ]);

        const body = el('div', { class: 'body' }, [titleRow]);
        if (subtitle) body.appendChild(el('div', { class: 'meta', text: subtitle }));
        if (metaParts.length) body.appendChild(el('div', { class: 'meta', text: metaParts.join(' · ') }));

        const idRow = el('div', { class: 'meta' }, ['ID ' + snap.vitrina_id]);
        if (snap.krisha_id) {
          idRow.appendChild(document.createTextNode(' · '));
          idRow.appendChild(el('a', {
            href: 'https://krisha.kz/a/show/' + encodeURIComponent(snap.krisha_id),
            target: '_blank',
            rel: 'noopener',
            text: 'krisha.kz',
          }));
        }
        body.appendChild(idRow);

        const syncWrap = el('div', { class: 'sync' });
        if (dryRun) {
          syncWrap.appendChild(el('span', { class: 'sync mute', text: 'Предпросмотр — сделка не создана' }));
        } else if (it.sync_status === 'success' && it.bitrix_lead_id) {
          syncWrap.appendChild(el('span', { class: 'sync ok' }, [
            '✓ Сделка ',
            el('a', {
              href: '/crm/deal/details/' + encodeURIComponent(it.bitrix_lead_id) + '/',
              target: '_top',
              text: '#' + it.bitrix_lead_id,
            }),
            ' создана',
          ]));
        } else if (it.sync_status === 'failed') {
          syncWrap.appendChild(el('span', { class: 'sync bad', text: '✗ Ошибка: ' + (it.sync_error || 'неизвестная ошибка') }));
        } else if (it.sync_status === 'pending') {
          syncWrap.appendChild(el('span', { class: 'sync mute', text: '⏳ В процессе…' }));
        } else {
          syncWrap.appendChild(el('span', { class: 'sync mute', text: 'не синхронизировано' }));
        }
        body.appendChild(syncWrap);

        return el('div', { class: 'item' }, [
          el('div', { class: 'pos', text: it.batch_position + '.' }),
          body,
          el('div', { class: 'price', text: formatPrice(snap.sell_price) }),
        ]);
      }

      function renderBatch(batch, dryRun) {
        const status = batch.assignment_status;
        const sync = batch.sync_status;
        const errorMsg = batch.error_message;

        if (status === 'preview') {
          showBanner('info', [el('strong', { text: 'Предпросмотр. ' }), 'Найдено ' + batch.assigned_count + ' объектов. Сделки ещё не созданы.']);
        } else if (status === 'assigned' && sync === 'success') {
          showBanner('ok', [el('strong', { text: 'Готово. ' }), 'Создано ' + batch.assigned_count + ' сделок в Bitrix.']);
        } else if (status === 'assigned' && sync === 'partial_failed') {
          showBanner('warn', [el('strong', { text: 'Частично. ' }), 'Назначено ' + batch.assigned_count + ', но часть сделок не создалась — см. ниже.']);
        } else if (status === 'assigned' && sync === 'failed') {
          showBanner('bad', [el('strong', { text: 'Сделки не созданы. ' }), 'Объекты помечены назначенными, но Bitrix вернул ошибку на каждую.']);
        } else if (status === 'blocked_limit') {
          showBanner('warn', '⚠ ' + (errorMsg || 'У вас 15+ открытых сделок в работе. Закройте часть в Bitrix и попробуйте снова.'));
        } else if (status === 'empty_supply') {
          showBanner('warn', '⚠ ' + (errorMsg || 'Свободных объектов для выдачи не найдено.'));
        } else if (status === 'failed') {
          showBanner('bad', '✗ ' + (errorMsg || 'Сбой при выдаче.'));
        } else {
          showBanner('info', String(status || ''));
        }

        clear(itemsNode);
        itemsNode.appendChild(renderSummary(batch));
        const items = batch.items || [];
        if (!items.length) {
          itemsNode.appendChild(el('div', { class: 'empty', text: 'Объектов в этой выдаче нет.' }));
          return;
        }
        for (const it of items) itemsNode.appendChild(renderItem(it, dryRun));
      }

      function renderOnboardingForm(data, dryRun) {
        clear(itemsNode);
        const wrap = el('div', { class: 'onboard' });
        const heading = el('div', { class: 'onboard-title', text: 'Привязка к агенту Vitrina' });
        const desc = el('div', { class: 'onboard-desc', text: 'Не удалось найти вас в базе агентов автоматически. Введите ваш рабочий номер телефона — мы привяжем ваш Bitrix-аккаунт к агенту.' });

        const nameLine = [data.last_name, data.name, data.second_name].filter(Boolean).join(' ');
        const fioNode = el('div', { class: 'onboard-fio' }, [
          el('span', { class: 'mute', text: 'ФИО из Bitrix: ' }),
          el('b', { text: nameLine || '(не определено)' }),
        ]);

        const input = el('input', {
          type: 'tel',
          inputmode: 'numeric',
          class: 'onboard-input',
          autocomplete: 'tel',
        });
        const PHONE_MASK = '+7 (___) ___-__-__';
        let enteredDigits = '';

        function formatPhone(digits) {
          let i = 0;
          let result = '';
          for (const ch of PHONE_MASK) {
            if (ch === '_') {
              result += i < digits.length ? digits[i] : '_';
              i++;
            } else {
              result += ch;
            }
          }
          return result;
        }

        function placeCaretAtFirstGap() {
          const firstUnderscore = input.value.indexOf('_');
          const pos = firstUnderscore === -1 ? input.value.length : firstUnderscore;
          input.setSelectionRange(pos, pos);
        }

        function render() {
          input.value = formatPhone(enteredDigits);
          placeCaretAtFirstGap();
        }

        function getEnteredDigits() { return enteredDigits; }

        render();

        input.addEventListener('keydown', function (e) {
          if (e.key === 'Backspace') {
            e.preventDefault();
            enteredDigits = enteredDigits.slice(0, -1);
            render();
            return;
          }
          if (e.ctrlKey || e.metaKey) return;
          if (/^[0-9]$/.test(e.key)) {
            e.preventDefault();
            if (enteredDigits.length < 10) {
              enteredDigits += e.key;
              render();
            }
            return;
          }
          if (['Tab', 'ArrowLeft', 'ArrowRight', 'Home', 'End', 'Shift'].includes(e.key)) return;
          e.preventDefault();
        });

        input.addEventListener('paste', function (e) {
          e.preventDefault();
          const text = (e.clipboardData || window.clipboardData).getData('text');
          let d = String(text || '').replace(/\D/g, '');
          if (d.length === 11 && (d[0] === '7' || d[0] === '8')) d = d.slice(1);
          enteredDigits = d.slice(0, 10);
          render();
        });

        input.addEventListener('focus', function () { setTimeout(placeCaretAtFirstGap, 0); });
        input.addEventListener('click', function () { placeCaretAtFirstGap(); });
        const submitBtn = el('button', { type: 'button', class: 'onboard-submit', text: 'Сохранить и продолжить' });
        const error = el('div', { class: 'onboard-error' });

        async function submit() {
          error.textContent = '';
          const digits = getEnteredDigits();
          if (digits.length !== 10) {
            error.textContent = 'Введите номер полностью (10 цифр после +7).';
            input.focus();
            return;
          }
          const raw = '+7' + digits;
          submitBtn.disabled = true;
          try {
            const r = await fetch('/api/v1/bitrix/onboard', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                bitrix_user_id: data.bitrix_user_id,
                phone: raw,
                name: data.name,
                last_name: data.last_name,
                second_name: data.second_name,
              }),
            });
            const body = await r.json();
            if (r.ok && body.success) {
              showBanner('ok', [el('strong', { text: 'Готово. ' }), 'Привязали Bitrix-аккаунт к ' + body.agent_phone + '. Запускаем выдачу…']);
              await runFlow(dryRun);
            } else if (r.status === 422) {
              error.textContent = (body && body.detail) || 'Неверный формат номера.';
              input.focus();
            } else if (r.status === 409) {
              showBanner('bad', '⚠ ' + ((body && body.detail) || 'Этот номер уже привязан к другому Bitrix-пользователю.'));
            } else {
              error.textContent = 'Ошибка ' + r.status + '. Попробуйте ещё раз.';
            }
          } catch (err) {
            error.textContent = 'Сетевая ошибка: ' + (err && err.message || err);
          } finally {
            submitBtn.disabled = false;
          }
        }

        submitBtn.addEventListener('click', submit);
        input.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });

        wrap.appendChild(heading);
        wrap.appendChild(desc);
        wrap.appendChild(fioNode);
        wrap.appendChild(el('div', { class: 'onboard-row' }, [input, submitBtn]));
        wrap.appendChild(error);
        itemsNode.appendChild(wrap);
        setTimeout(function () { input.focus(); }, 50);
      }

      async function runFlow(dryRun) {
        const context = buildContext();
        if (!context.bitrix_user_id) {
          showBanner('bad', 'Не удалось определить текущего Bitrix-пользователя. Перезагрузите страницу.');
          return;
        }

        btnPreview.disabled = true;
        btnRun.disabled = true;
        clear(itemsNode);
        showBanner('info', [el('span', { class: 'spinner' }), dryRun ? 'Получаем предпросмотр…' : 'Создаём сделки в Bitrix…']);

        try {
          const response = await fetch('/api/v1/bitrix/deal-toolbar/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...context, dry_run: dryRun }),
          });
          const payload = await response.json();

          if (response.ok && payload && payload.status === 'needs_onboarding') {
            clear(statusNode);
            renderOnboardingForm(payload, dryRun);
            return;
          }

          if ((response.ok || response.status === 409) && payload.batch) {
            renderBatch(payload.batch, dryRun);
          } else if (response.status === 404) {
            showBanner('bad', 'Не настроен маппинг для Bitrix-пользователя ' + context.bitrix_user_id + '. Обратитесь к администратору.');
          } else if (payload && payload.detail) {
            const detail = typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail);
            showBanner('bad', 'Ошибка ' + response.status + ': ' + detail);
          } else {
            showBanner('bad', 'Ошибка ' + response.status + '. Повторите попытку позже.');
          }
        } catch (err) {
          showBanner('bad', 'Сетевая ошибка: ' + (err && err.message || err));
        } finally {
          btnPreview.disabled = false;
          btnRun.disabled = false;
        }
      }

      btnPreview.addEventListener('click', function () { runFlow(true); });
      btnRun.addEventListener('click', function () { runFlow(false); });

      if (window.BX24) {
        BX24.init(function () {
          BX24.callMethod('user.current', {}, function (result) {
            if (result.error()) {
              userNode.textContent = 'Не удалось получить пользователя: ' + result.error();
              return;
            }
            currentUser = result.data();
            const full = [currentUser.NAME, currentUser.LAST_NAME].filter(Boolean).join(' ');
            userNode.textContent = 'Bitrix-пользователь: ' + (full || currentUser.ID) + ' (' + currentUser.ID + ')';
          });
        });
      } else {
        showBanner('bad', 'BX24 SDK не загрузился. Откройте страницу через приложение в Bitrix24.');
      }
    </script>
  </body>
</html>"""


@api_router.post("/install")
async def install_bitrix_app(
    request: Request,
    service: BitrixPlacementService = Depends(get_bitrix_placement_service),
):
    try:
        payload = await _parse_install_payload(request)
        await service.install(payload)
        return HTMLResponse(_INSTALL_FINISH_HTML)
    except BitrixSyncConfigurationError as exc:
        logger.warning("Bitrix install rejected: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        logger.warning("Bitrix install payload invalid: %s", exc.errors())
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        logger.warning("Bitrix install payload invalid: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Bitrix install failed: placement API error")
        raise HTTPException(status_code=502, detail=f"Bitrix API error: {exc}") from exc


@api_router.post("/uninstall", response_model=BitrixInstallResponse)
async def uninstall_bitrix_app(
    request: Request,
    service: BitrixPlacementService = Depends(get_bitrix_placement_service),
):
    try:
        payload = await _parse_install_payload(request)
        return BitrixInstallResponse.model_validate(await service.uninstall(payload))
    except BitrixSyncConfigurationError as exc:
        logger.warning("Bitrix uninstall rejected: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        logger.warning("Bitrix uninstall payload invalid: %s", exc.errors())
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        logger.warning("Bitrix uninstall payload invalid: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Bitrix uninstall failed: placement API error")
        raise HTTPException(status_code=502, detail=f"Bitrix API error: {exc}") from exc


@api_router.post(
    "/deal-toolbar/run",
    responses={409: {"model": AssignmentConflictResponse}},
)
async def run_bitrix_toolbar_flow(
    payload: BitrixToolbarRunRequest,
    mapping_service: AgentMappingService = Depends(get_mapping_service),
    assignment_service: AssignmentService = Depends(get_assignment_service),
    sync_service: BitrixDealSyncService = Depends(get_bitrix_deal_sync_service),
    session: AsyncSession = Depends(get_db_session),
):
    context = BitrixExecutionContext(
        portal_domain=payload.portal_domain,
        access_token=payload.access_token,
        refresh_token=payload.refresh_token,
        member_id=payload.member_id,
        placement=payload.placement,
    )

    try:
        await mapping_service.resolve_or_auto_bind(payload.bitrix_user_id, payload.profile)
        await session.commit()
    except OnboardingRequiredSignal as signal:
        return JSONResponse(
            status_code=200,
            content=jsonable_encoder(
                BitrixNeedsOnboardingResponse(
                    bitrix_user_id=signal.bitrix_user_id,
                    suggested_full_name=signal.suggested_full_name,
                    name=signal.name,
                    last_name=signal.last_name,
                    second_name=signal.second_name,
                )
            ),
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


@api_router.post("/onboard", response_model=BitrixOnboardResponse)
async def bitrix_onboard(
    payload: BitrixOnboardRequest,
    mapping_service: AgentMappingService = Depends(get_mapping_service),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        mapping, created_new = await mapping_service.onboard(
            bitrix_user_id=payload.bitrix_user_id,
            raw_phone=payload.phone,
            name=payload.name,
            last_name=payload.last_name,
            second_name=payload.second_name,
        )
        await session.commit()
        return BitrixOnboardResponse(
            success=True,
            agent_phone=mapping.agent_phone,
            full_name=mapping.full_name,
            created_new_agent=created_new,
        )
    except InvalidPhoneError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PhoneAlreadyBoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@ui_router.api_route("/bitrix/toolbar", methods=["GET", "POST"], response_class=HTMLResponse)
async def bitrix_toolbar_page(settings=Depends(get_settings_dependency)) -> HTMLResponse:
    html = _TOOLBAR_HTML_TEMPLATE.replace(
        "__PORTAL_DOMAIN__", settings.bitrix_portal_domain or ""
    )
    return HTMLResponse(html, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


