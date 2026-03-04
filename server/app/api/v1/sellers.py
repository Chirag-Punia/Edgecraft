from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.seller import SellerUpdate, SellerResponse
from app.services import seller_service

router = APIRouter(prefix="/sellers", tags=["sellers"])


@router.get("/me", response_model=SellerResponse)
def get_my_seller(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return seller_service.get_seller(db, current_user)


@router.put("/me", response_model=SellerResponse)
def update_my_seller(
    body: SellerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return seller_service.upsert_seller(db, current_user, body)
