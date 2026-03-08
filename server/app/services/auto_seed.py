"""Auto-seed demo data for newly onboarded users."""
import logging

from app.db.session import SessionLocal
from app.enums import Marketplace, AccountStatus, SyncRunStatus, SyncType
from app.models.marketplace_account import MarketplaceAccount
from app.models.sync_run import SyncRun
from app.models.user import User
from app.services.sync_worker import run_sync

logger = logging.getLogger(__name__)


def auto_seed_for_user(user_id: int):
    """Background task: create demo marketplace account and run mock sync."""
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if not user or not user.seller_id:
            logger.warning("auto_seed: user %s has no seller_id, skipping", user_id)
            return

        seller_id = user.seller_id

        # Idempotency: skip if demo account with a completed or running sync exists
        existing = (
            db.query(MarketplaceAccount)
            .filter_by(seller_id=seller_id, is_demo_data=True)
            .join(SyncRun, SyncRun.marketplace_account_id == MarketplaceAccount.id)
            .filter(SyncRun.status.in_([SyncRunStatus.COMPLETED, SyncRunStatus.RUNNING]))
            .first()
        )
        if existing:
            logger.info("auto_seed: demo data already exists for seller %s, skipping", seller_id)
            return

        # Create or reuse Amazon marketplace account
        account = (
            db.query(MarketplaceAccount)
            .filter_by(seller_id=seller_id, marketplace=Marketplace.AMAZON)
            .first()
        )
        if not account:
            account = MarketplaceAccount(
                seller_id=seller_id,
                marketplace=Marketplace.AMAZON,
                status=AccountStatus.CONNECTED,
                is_demo_data=True,
            )
            db.add(account)
            db.flush()
        elif not account.is_demo_data:
            # Real account exists via OAuth — don't overwrite it
            logger.info("auto_seed: real Amazon account exists for seller %s, skipping", seller_id)
            return
        else:
            account.status = AccountStatus.CONNECTED

        account.last_sync_at = None
        db.commit()
        db.refresh(account)

        logger.info("auto_seed: running mock sync for user %s, account %s", user_id, account.id)
        run_sync(db, account.id, sync_type=SyncType.FULL, force_mock=True)

    except Exception:
        logger.exception("auto_seed failed for user %s", user_id)
    finally:
        db.close()
