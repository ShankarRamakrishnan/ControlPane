import logging
from typing import Any

from gateway.adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


class CapabilityRegistry:
    """
    Maps adapter types to adapter instances and dispatches output delivery.

    The registry is intentionally decoupled from manifest models so it can be
    used without importing the full manifest graph. Callers pass a ProviderDef
    (or any object with .type and .config) directly.
    """

    def __init__(self):
        self._adapters: dict[str, BaseAdapter] = {}

    def register(self, adapter_type: str, adapter: BaseAdapter) -> None:
        self._adapters[adapter_type] = adapter
        logger.debug(f"Registered adapter: {adapter_type}")

    def registered_types(self) -> list[str]:
        return list(self._adapters.keys())

    async def deliver(self, provider, payload: dict[str, Any], output_name: str) -> None:
        """
        Resolve the adapter for provider.type and deliver the payload.

        Args:
            provider:    A ProviderDef (has .type and .config).
            payload:     The data to send.
            output_name: Used only for log messages.
        """
        adapter = self._adapters.get(provider.type)
        if not adapter:
            raise ValueError(
                f"Output '{output_name}': no adapter registered for type '{provider.type}'. "
                f"Available: {self.registered_types()}"
            )
        await adapter.deliver(payload, provider.config)
        logger.info(f"Output '{output_name}' delivered via adapter '{provider.type}'")
