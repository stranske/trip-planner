"""Request and response shapes for human-entered trip prices."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TripPriceComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str
    label: str
    currency: str
    #: None when nobody has priced this component. Never 0.0 as a stand-in for absent.
    typical_amount: float | None = None
    note: str = ""
    price_source: dict[str, str] | None = None


class TripPriceTotal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    typical_amount: float
    currency: str
    price_source: dict[str, str]


class TripPricesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    components: list[TripPriceComponent]
    total: TripPriceTotal | None = None
    priced_component_count: int
    unpriced_component_count: int


class TripPriceUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str
    #: Omit or send null to withdraw a figure that turned out to be wrong.
    amount: float | None = None
    currency: str = "USD"
    note: str = Field(default="", max_length=400)
