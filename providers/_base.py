from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod


@dataclasses.dataclass
class PropertySearchParams:
    location: str
    listing_type: str = "for_sale"
    home_types: list[str] = dataclasses.field(default_factory=lambda: ["Houses"])
    min_price: int = 0
    max_price: int = 1_000_000
    min_beds: int = 0
    min_baths: int = 0
    max_results: int = 20


@dataclasses.dataclass
class NormalizedProperty:
    source: str
    property_id: str
    address: str
    price: float | None
    beds: float | None
    baths: float | None
    sqft: float | None
    lot_size_sqft: float | None
    home_type: str | None
    year_built: int | None
    days_on_market: int | None
    price_per_sqft: float | None
    estimated_value: float | None
    estimated_rent: float | None
    hoa_fee: float | None
    listing_status: str | None
    url: str | None
    latitude: float | None
    longitude: float | None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


class RealEstateProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def search(self, params: PropertySearchParams) -> list[NormalizedProperty]:
        ...

    def is_available(self) -> bool:
        return True
