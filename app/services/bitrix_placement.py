from __future__ import annotations

from app.bitrix.client import BitrixApiClient
from app.config import Settings
from app.exceptions import BitrixSyncConfigurationError
from app.schemas.bitrix import BitrixExecutionContext, BitrixInstallPayload


class BitrixPlacementService:
    def __init__(self, settings: Settings, client: BitrixApiClient) -> None:
        self.settings = settings
        self.client = client

    async def install(self, payload: BitrixInstallPayload) -> dict:
        if not self.settings.bitrix_enabled:
            raise BitrixSyncConfigurationError("Bitrix integration is disabled.")
        if not self.settings.bitrix_toolbar_url:
            raise BitrixSyncConfigurationError("BITRIX_APP_PUBLIC_BASE_URL is not configured.")

        context = BitrixExecutionContext(
            portal_domain=payload.portal_domain,
            access_token=payload.access_token,
            refresh_token=payload.refresh_token,
            member_id=payload.member_id,
        )
        try:
            await self.client.unbind_toolbar_placement(context)
        except RuntimeError:
            pass
        details = await self.client.bind_toolbar_placement(context, self.settings.bitrix_toolbar_url)
        return {
            "success": True,
            "placement": "CRM_DEAL_LIST_TOOLBAR",
            "handler_url": self.settings.bitrix_toolbar_url,
            "details": details,
        }

    async def uninstall(self, payload: BitrixInstallPayload) -> dict:
        if not self.settings.bitrix_enabled:
            raise BitrixSyncConfigurationError("Bitrix integration is disabled.")
        context = BitrixExecutionContext(
            portal_domain=payload.portal_domain,
            access_token=payload.access_token,
            refresh_token=payload.refresh_token,
            member_id=payload.member_id,
        )
        details = await self.client.unbind_toolbar_placement(context)
        return {
            "success": True,
            "placement": "CRM_DEAL_LIST_TOOLBAR",
            "handler_url": self.settings.bitrix_toolbar_url,
            "details": details,
        }

