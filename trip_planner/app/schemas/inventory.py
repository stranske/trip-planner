from typing import Any

from pydantic import BaseModel, Field


class InventoryResponse(BaseModel):
    trip_id: str = Field(description="Trip whose inventory bundles were assembled.")
    bundle_count: int = Field(description="Number of assembled bundles currently available.")
    bundles: list[dict[str, Any]] = Field(
        description="Full InventoryBundle payloads assembled from normalized option contracts."
    )
    summary: dict[str, Any] = Field(
        description="Workspace-ready inventory summary derived from the assembled bundles."
    )
