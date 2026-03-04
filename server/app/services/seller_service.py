from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.seller import Seller
from app.models.user import User
from app.schemas.seller import SellerUpdate


def get_seller(db: Session, user: User) -> Seller:
    if not user.seller_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business profile found")
    seller = db.query(Seller).filter(Seller.id == user.seller_id).first()
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    return seller


def upsert_seller(db: Session, user: User, data: SellerUpdate) -> Seller:
    if user.seller_id:
        seller = db.query(Seller).filter(Seller.id == user.seller_id).first()
        if seller:
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(seller, field, value)
            db.commit()
            db.refresh(seller)
            return seller

    # Create new seller
    seller = Seller(**data.model_dump())
    db.add(seller)
    db.commit()
    db.refresh(seller)

    user.seller_id = seller.id
    db.commit()

    return seller
