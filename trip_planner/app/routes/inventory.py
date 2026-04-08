from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from trip_planner.app.schemas.inventory import InventoryResponse
from trip_planner.app.services.auth import AuthenticatedUser, require_authenticated_user
from trip_planner.app.services.inventory import get_inventory_payload
from trip_planner.persistence.db import get_db_session

router = APIRouter(tags=["inventory"])


@router.get("/inventory/{trip_id}", response_model=InventoryResponse)
def read_inventory(
    trip_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> InventoryResponse:
    payload = get_inventory_payload(db_session, user=user, trip_id=trip_id)
    if payload is None:
        raise HTTPException(
            status_code=404, detail=f"Inventory bundles for trip '{trip_id}' were not found."
        )
    return InventoryResponse.model_validate(payload)
