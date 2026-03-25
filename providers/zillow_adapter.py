from __future__ import annotations

import os

import httpx

from providers._base import NormalizedProperty, PropertySearchParams, RealEstateProvider

_STATUS_MAP = {
    "for_sale": "forSale",
    "for_rent": "forRent",
}

_HOME_TYPE_MAP = {
    "All": "",
    "Houses": "Houses",
    "Condos": "Condos",
    "Townhomes": "Townhomes",
    "MultiFamily": "MultiFamily",
}


class ZillowRapidAPIAdapter(RealEstateProvider):
    name = "zillow_rapidapi"

    def is_available(self) -> bool:
        return bool(os.getenv("RAPIDAPI_KEY"))

    def search(self, params: PropertySearchParams) -> list[NormalizedProperty]:
        api_key = os.getenv("RAPIDAPI_KEY")

        home_type_values = [_HOME_TYPE_MAP.get(ht, ht) for ht in params.home_types]
        home_type_str = ",".join(filter(None, home_type_values)) or ""

        query: dict[str, str] = {
            "location": params.location,
            "status_type": _STATUS_MAP.get(params.listing_type, "forSale"),
        }
        if home_type_str:
            query["home_type"] = home_type_str
        if params.min_price > 0:
            query["minPrice"] = str(params.min_price)
        if params.max_price:
            query["maxPrice"] = str(params.max_price)
        if params.min_beds > 0:
            query["bedsMin"] = str(params.min_beds)
        if params.min_baths > 0:
            query["bathsMin"] = str(params.min_baths)

        resp = httpx.get(
            "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch",
            params=query,
            headers={
                "X-RapidAPI-Key": api_key,
                "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com",
            },
            timeout=15,
        )
        if resp.is_error:
            raise RuntimeError(f"Zillow API HTTP error: {resp.status_code} - {resp.text}")

        data = resp.json()
        props_raw = data.get("props", [])

        results: list[NormalizedProperty] = []
        for p in props_raw[: params.max_results]:
            price = p.get("price")
            sqft = p.get("livingArea")
            price_per_sqft = round(price / sqft, 2) if price and sqft else None
            detail_url = p.get("detailUrl", "")
            url = f"https://www.zillow.com{detail_url}" if detail_url else None

            results.append(
                NormalizedProperty(
                    source="zillow_rapidapi",
                    property_id=str(p.get("zpid", "")),
                    address=p.get("address", ""),
                    price=float(price) if price is not None else None,
                    beds=float(p["bedrooms"]) if p.get("bedrooms") is not None else None,
                    baths=float(p["bathrooms"]) if p.get("bathrooms") is not None else None,
                    sqft=float(sqft) if sqft is not None else None,
                    lot_size_sqft=float(p["lotAreaValue"]) if p.get("lotAreaValue") is not None else None,
                    home_type=p.get("homeType"),
                    year_built=p.get("yearBuilt"),
                    days_on_market=p.get("daysOnZillow"),
                    price_per_sqft=price_per_sqft,
                    estimated_value=float(p["zestimate"]) if p.get("zestimate") is not None else None,
                    estimated_rent=float(p["rentZestimate"]) if p.get("rentZestimate") is not None else None,
                    hoa_fee=float(p["hoaFee"]) if p.get("hoaFee") is not None else None,
                    listing_status=p.get("listingStatus"),
                    url=url,
                    latitude=p.get("latitude"),
                    longitude=p.get("longitude"),
                )
            )

        return results
