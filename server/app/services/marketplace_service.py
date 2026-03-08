import json
import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.enums import Marketplace, AccountStatus
from app.models.marketplace_account import MarketplaceAccount

logger = logging.getLogger(__name__)


def create_marketplace(db: Session, seller_id: int, marketplace: Marketplace, credentials: dict | None) -> MarketplaceAccount:
    existing = (
        db.query(MarketplaceAccount)
        .filter(MarketplaceAccount.seller_id == seller_id, MarketplaceAccount.marketplace == marketplace)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{marketplace.value} already connected")

    account = MarketplaceAccount(
        seller_id=seller_id,
        marketplace=marketplace,
        status=AccountStatus.CONNECTED,
        credentials_encrypted=json.dumps(credentials) if credentials else None,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def list_marketplaces(db: Session, seller_id: int, include_demo: bool = False) -> list[MarketplaceAccount]:
    query = db.query(MarketplaceAccount).filter(MarketplaceAccount.seller_id == seller_id)
    if not include_demo:
        query = query.filter(MarketplaceAccount.is_demo_data.is_(False))
    return query.all()


def connect_amazon_oauth(
    db: Session, seller_id: int, selling_partner_id: str, refresh_token: str
) -> MarketplaceAccount:
    """Create or update an Amazon marketplace account after successful OAuth."""
    logger.info("[Marketplace] connect_amazon_oauth called: seller_id=%s, selling_partner_id=%s", seller_id, selling_partner_id)
    creds = json.dumps({"refresh_token": refresh_token, "selling_partner_id": selling_partner_id})

    existing = (
        db.query(MarketplaceAccount)
        .filter(MarketplaceAccount.seller_id == seller_id, MarketplaceAccount.marketplace == Marketplace.AMAZON)
        .first()
    )

    if existing:
        logger.info("[Marketplace] Existing Amazon account found: id=%s, old_status=%s — updating credentials", existing.id, existing.status)
        existing.credentials_encrypted = creds
        existing.status = AccountStatus.CONNECTED
        existing.is_demo_data = False
    else:
        logger.info("[Marketplace] No existing Amazon account — creating new for seller_id=%s", seller_id)
        existing = MarketplaceAccount(
            seller_id=seller_id,
            marketplace=Marketplace.AMAZON,
            status=AccountStatus.CONNECTED,
            credentials_encrypted=creds,
            is_demo_data=False,
        )
        db.add(existing)

    db.commit()
    db.refresh(existing)
    logger.info("[Marketplace] Amazon account saved: id=%s, status=%s", existing.id, existing.status)
    return existing


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
