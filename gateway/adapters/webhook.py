import os
import logging
from typing import Any

import httpx

from gateway.adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


class WebhookAdapter(BaseAdapter):
    """Delivers payloads via HTTP POST.

    Config keys:
      url      — literal URL to POST to
      url_env  — name of an env var holding the URL (e.g. "SLACK_WEBHOOK_URL")
    """

    async def deliver(self, payload: dict[str, Any], config: dict[str, Any]) -> None:
        url = config.get("url") or os.getenv(config.get("url_env", ""), "")
        if not url:
            raise ValueError(
                "WebhookAdapter requires 'url' or 'url_env' in provider config"
            )
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=30)
            resp.raise_for_status()
