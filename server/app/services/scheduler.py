"""APScheduler-based background sync scheduler."""
import logging
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.db.session import SessionLocal
from app.enums import Marketplace, AccountStatus, SyncType
from app.models.marketplace_account import MarketplaceAccount
from app.services.sync_worker import run_sync

logger = logging.getLogger(__name__)
settings = get_settings()

_scheduler: BackgroundScheduler | None = None


def scheduled_sync_all():
    """Run sync for all connected Amazon marketplace accounts."""
    db = SessionLocal()
    try:
        accounts = db.query(MarketplaceAccount).filter(
            MarketplaceAccount.marketplace == Marketplace.AMAZON,
            MarketplaceAccount.status == AccountStatus.CONNECTED,
        ).all()
        logger.info(f"Scheduled sync: found {len(accounts)} connected Amazon accounts")
        for account in accounts:
            try:
                run_sync(db, account.id, sync_type=SyncType.FULL)
            except Exception:
                logger.exception(f"Scheduled sync failed for account {account.id}")
    finally:
        db.close()


def start_scheduler():
    """Start the background scheduler."""
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        scheduled_sync_all,
        "interval",
        hours=settings.SYNC_INTERVAL_HOURS,
        id="amazon_sync",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(f"Scheduler started: syncing every {settings.SYNC_INTERVAL_HOURS}h")


def shutdown_scheduler():
    """Shutdown the background scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler shut down")
