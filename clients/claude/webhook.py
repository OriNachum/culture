# clients/claude/webhook.py
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class WebhookClient:
    """Fire-and-forget webhook notifications via aiohttp."""

    def __init__(self) -> None:
        self._session = None

    async def _get_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session

    async def post(self, url: str | None, payload: dict) -> None:
        if not url:
            return
        try:
            import aiohttp
            session = await self._get_session()
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)):
                pass
        except Exception:
            logger.debug("Webhook POST to %s failed (non-fatal)", url)

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
