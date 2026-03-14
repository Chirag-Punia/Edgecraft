from fastapi import APIRouter, BackgroundTasks, Depends

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.schemas.seller import SellerUpdate, SellerResponse
from app.services import seller_service
from app.services.auto_seed import auto_seed_for_user

router = APIRouter(prefix="/sellers", tags=["sellers"])


@router.get("/me", response_model=SellerResponse)
def get_my_seller(current_user=Depends(get_current_user), db=Depends(get_db)):
    return seller_service.get_seller(db, current_user)


@router.put("/me", response_model=SellerResponse)
def update_my_seller(body: SellerUpdate, background_tasks: BackgroundTasks,
                     current_user=Depends(get_current_user), db=Depends(get_db)):
    is_new = current_user.seller_id is None
    result = seller_service.upsert_seller(db, current_user, body)
    if is_new:
        background_tasks.add_task(auto_seed_for_user, current_user.id)
    return result
