import json

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.marketplace_account import MarketplaceAccount

VALID_MARKETPLACES = {"amazon", "flipkart", "shopify", "facebook"}


def create_marketplace(db: Session, seller_id: int, marketplace: str, credentials: dict | None) -> MarketplaceAccount:
    if marketplace not in VALID_MARKETPLACES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid marketplace: {marketplace}")

    existing = (
        db.query(MarketplaceAccount)
        .filter(MarketplaceAccount.seller_id == seller_id, MarketplaceAccount.marketplace == marketplace)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{marketplace} already connected")

    account = MarketplaceAccount(
        seller_id=seller_id,
        marketplace=marketplace,
        status="connected",
        credentials_encrypted=json.dumps(credentials) if credentials else None,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def list_marketplaces(db: Session, seller_id: int) -> list[MarketplaceAccount]:
    return db.query(MarketplaceAccount).filter(MarketplaceAccount.seller_id == seller_id).all()


def delete_marketplace(db: Session, seller_id: int, marketplace_id: int) -> None:
    account = (
        db.query(MarketplaceAccount)
        .filter(MarketplaceAccount.id == marketplace_id, MarketplaceAccount.seller_id == seller_id)
        .first()
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marketplace account not found")
    db.delete(account)
    db.commit()
