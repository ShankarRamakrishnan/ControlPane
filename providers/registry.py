from __future__ import annotations

import logging

from providers._base import NormalizedProperty, PropertySearchParams, RealEstateProvider
from providers.bridge_adapter import ZillowBridgeAdapter
from providers.zillow_adapter import ZillowRapidAPIAdapter

# Phase 3 extension point: MCP-backed providers will implement RealEstateProvider
# and can be registered here alongside native Python adapters.
# The broker does not need to know whether the backend is local Python, REST, or MCP.

logger = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self, providers: list[RealEstateProvider]):
        self._providers = providers

    def available_providers(self) -> list[str]:
        return [p.name for p in self._providers if p.is_available()]

    def search(self, params: PropertySearchParams) -> tuple[list[NormalizedProperty], str]:
        for provider in self._providers:
            if not provider.is_available():
                continue
            try:
                results = provider.search(params)
                if results:
                    return results, provider.name
            except Exception as exc:
                logger.warning("Provider %s raised an exception: %s", provider.name, exc)
        return [], "none"


default_registry = ProviderRegistry([ZillowRapidAPIAdapter(), ZillowBridgeAdapter()])
