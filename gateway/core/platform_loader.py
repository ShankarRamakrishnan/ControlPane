from __future__ import annotations

import dataclasses
import logging
import os

import httpx
import yaml

from gateway.models.platform_manifest import BindingDef, PlatformManifest, ProviderDef
from providers._base import NormalizedProperty

logger = logging.getLogger(__name__)

_engine: PlatformEngine | None = None


def initialize(platform_yaml_path: str, plugin_registry=None) -> "PlatformEngine":
    global _engine
    with open(platform_yaml_path) as f:
        raw = yaml.safe_load(f)
    manifest = PlatformManifest.model_validate(raw)
    _engine = PlatformEngine(manifest, plugin_registry=plugin_registry)
    return _engine


def get_engine() -> "PlatformEngine | None":
    return _engine


class PlatformEngine:
    def __init__(self, manifest: PlatformManifest, plugin_registry=None):
        self._manifest = manifest
        self._plugins = plugin_registry
        self._providers: dict[str, ProviderDef] = {p.name: p for p in manifest.providers}
        self._bindings: dict[tuple[str, str], BindingDef] = {
            (b.capability, b.provider): b for b in manifest.bindings
        }

    def get_agent_permissions(self, agent_name: str):
        """Return AgentPermissions for the named agent, or None."""
        for a in self._manifest.agents:
            if a.name == agent_name:
                return a
        return None

    def providers_for_capability(self, capability: str) -> list[str]:
        """Return names of active (non-stub) providers that support this capability."""
        return [
            p.name for p in self._manifest.providers
            if capability in p.supports and p.status == "active"
        ]

    def invoke_capability(self, capability: str, params: dict) -> list:
        routing = self._manifest.policies.routing.get(capability)
        if routing:
            order = routing.order
        else:
            order = [p.name for p in self._manifest.providers if capability in p.supports]

        for provider_name in order:
            provider = self._providers.get(provider_name)
            if not provider:
                logger.warning("Provider %s not found in manifest, skipping", provider_name)
                continue

            if provider.status == "stub":
                logger.debug("Provider %s is a stub, skipping", provider_name)
                continue

            if not self._is_available(provider):
                logger.debug("Provider %s is not available (missing secret), skipping", provider_name)
                continue

            binding = self._bindings.get((capability, provider_name))
            if not binding:
                logger.debug("No binding for (%s, %s), skipping", capability, provider_name)
                continue

            try:
                results = self._invoke_http(provider, binding, params)
                if results:
                    return results
            except Exception as exc:
                logger.warning("Provider %s raised an exception: %s", provider_name, exc)
                continue

        if self._plugins is not None:
            from providers._base import PropertySearchParams
            params_obj = PropertySearchParams(
                location=params.get("location", ""),
                listing_type=params.get("listing_type", "for_sale"),
                home_types=[ht.strip() for ht in str(params.get("home_types", "Houses")).split(",")],
                min_price=params.get("min_price", 0),
                max_price=params.get("max_price", 1_000_000),
                min_beds=params.get("min_beds", 0),
                min_baths=params.get("min_baths", 0),
                max_results=params.get("max_results", 20),
            )
            results, _ = self._plugins.search(params_obj)
            return results

        return []

    def _is_available(self, provider: ProviderDef) -> bool:
        if provider.auth is None:
            return True
        if provider.auth.secret is None:
            return True
        return bool(os.getenv(provider.auth.secret))

    def _invoke_http(self, provider: ProviderDef, binding: BindingDef, params: dict) -> list:
        provider_params: dict[str, str] = {}
        for provider_field, canonical_field in binding.input_map.items():
            value = params.get(canonical_field)
            if value is None:
                continue
            if value == 0 and canonical_field not in ("max_price", "max_results"):
                continue
            if canonical_field in binding.value_maps:
                value = binding.value_maps[canonical_field].get(str(value), value)
            provider_params[provider_field] = str(value)

        headers: dict[str, str] = {}
        if provider.auth:
            secret_val = os.getenv(provider.auth.secret, "") if provider.auth.secret else ""
            for header_name, header_template in provider.auth.headers.items():
                headers[header_name] = header_template.replace("{{secret}}", secret_val)

        url = provider.transport.base_url.rstrip("/") + binding.operation

        resp = httpx.get(url, params=provider_params, headers=headers, timeout=15)
        if resp.is_error:
            raise RuntimeError(f"HTTP error from {provider.name}: {resp.status_code} - {resp.text}")

        data = resp.json()
        if binding.results_key:
            items = data.get(binding.results_key, [])
        else:
            items = data

        max_results = params.get("max_results", 20)
        return [self._normalize_item(item, binding, provider.name) for item in items[:max_results]]

    def _normalize_item(self, item: dict, binding: BindingDef, source: str) -> NormalizedProperty:
        float_fields = (
            "price", "beds", "baths", "sqft", "lot_size_sqft",
            "estimated_value", "estimated_rent", "hoa_fee", "latitude", "longitude",
        )
        int_fields = ("year_built", "days_on_market")
        str_fields = ("property_id",)

        valid_fields = {f.name for f in dataclasses.fields(NormalizedProperty)}
        kwargs: dict = {f.name: None for f in dataclasses.fields(NormalizedProperty)}
        kwargs["source"] = source

        for canonical_field, provider_field in binding.output_map.items():
            value = item.get(provider_field)
            if canonical_field in binding.url_prefixes and value:
                value = binding.url_prefixes[canonical_field] + value
            if value is not None:
                if canonical_field in float_fields:
                    value = float(value)
                elif canonical_field in int_fields:
                    value = int(value)
                elif canonical_field in str_fields:
                    value = str(value)
            if canonical_field in valid_fields:
                kwargs[canonical_field] = value

        price = kwargs.get("price")
        sqft = kwargs.get("sqft")
        if price and sqft and sqft > 0:
            kwargs["price_per_sqft"] = round(price / sqft, 2)

        return NormalizedProperty(**{k: v for k, v in kwargs.items() if k in valid_fields})
