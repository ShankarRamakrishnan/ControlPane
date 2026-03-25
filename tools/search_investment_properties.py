import json
import logging

from langchain_core.tools import tool

from gateway.core.tool_registry import register

logger = logging.getLogger(__name__)


@register
@tool
def search_investment_properties(
    location: str,
    listing_type: str = "for_sale",
    home_types: str = "Houses",
    min_price: int = 0,
    max_price: int = 1_000_000,
    min_beds: int = 0,
    min_baths: int = 0,
    max_results: int = 20,
) -> str:
    """Search for investment properties across available real estate data providers. Returns a JSON object with 'properties' (list), 'total' (int), and 'provider' (str, which backend was used). home_types is a comma-separated string of: Houses, Condos, Townhomes, MultiFamily, All."""

    params = {
        "location": location,
        "listing_type": listing_type,
        "home_types": home_types,
        "min_price": min_price,
        "max_price": max_price,
        "min_beds": min_beds,
        "min_baths": min_baths,
        "max_results": max_results,
    }

    # Try manifest-driven platform engine first
    from gateway.core.platform_loader import get_engine
    engine = get_engine()
    if engine:
        results = engine.invoke_capability("real_estate.find_candidates", params)
        if results:
            return json.dumps({
                "properties": [r.to_dict() for r in results],
                "total": len(results),
                "provider": "platform",
            })

    # Fallback: Python provider registry
    from providers._base import PropertySearchParams
    from providers.registry import default_registry
    search_params = PropertySearchParams(
        location=location,
        listing_type=listing_type,
        home_types=[ht.strip() for ht in home_types.split(",")],
        min_price=min_price,
        max_price=max_price,
        min_beds=min_beds,
        min_baths=min_baths,
        max_results=max_results,
    )
    results, provider_name = default_registry.search(search_params)
    if not results:
        return json.dumps({"properties": [], "total": 0, "provider": provider_name, "message": "No listings found."})
    return json.dumps({"properties": [r.to_dict() for r in results], "total": len(results), "provider": provider_name})
