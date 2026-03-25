from __future__ import annotations

import os

from providers._base import NormalizedProperty, PropertySearchParams, RealEstateProvider


class ZillowBridgeAdapter(RealEstateProvider):
    name = "zillow_bridge"

    def is_available(self) -> bool:
        return bool(os.getenv("ZILLOW_BRIDGE_API_KEY"))

    def search(self, params: PropertySearchParams) -> list[NormalizedProperty]:
        raise NotImplementedError(
            "ZillowBridgeAdapter is not yet implemented — request credentials at api@bridgeinteractive.com"
        )
