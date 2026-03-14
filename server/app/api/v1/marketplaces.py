from fastapi import APIRouter, Depends, HTTPException, status

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.schemas.marketplace import MarketplaceCreate, MarketplaceResponse
from app.schemas.auth import MessageResponse
from app.services import marketplace_service

router = APIRouter(prefix="/marketplaces", tags=["marketplaces"])


@router.post("", response_model=MarketplaceResponse)
def connect_marketplace(
    body: MarketplaceCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    if not current_user.seller_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Complete business setup first")
    return marketplace_service.create_marketplace(db, current_user.seller_id, body.marketplace, body.credentials)


@router.get("", response_model=list[MarketplaceResponse])
def list_marketplaces(
    include_demo: bool = False,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    if not current_user.seller_id:
        return []
    return marketplace_service.list_marketplaces(db, current_user.seller_id, include_demo=include_demo)


@router.delete("/{marketplace_id}", response_model=MessageResponse)
def disconnect_marketplace(
    marketplace_id: int,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    if not current_user.seller_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No business profile")
    marketplace_service.delete_marketplace(db, current_user.seller_id, marketplace_id)
    return {"message": "Marketplace disconnected"}
