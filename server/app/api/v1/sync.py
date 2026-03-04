"""Sync API endpoints — trigger syncs, view run history, seed demo data."""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import SessionLocal, get_db
from app.models.marketplace_account import MarketplaceAccount
from app.models.seller import Seller
from app.models.sync_run import SyncRun
from app.models.user import User
from app.schemas.sync import SyncTriggerRequest, SyncRunResponse, SyncTriggerResponse, SeedDemoResponse
from app.services.sync_worker import run_sync

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["sync"])


def _run_sync_background(marketplace_account_id: int, sync_type: str):
    """Background task wrapper — uses its own DB session."""
    db = SessionLocal()
    try:
        run_sync(db, marketplace_account_id, sync_type)
    finally:
        db.close()


@router.post("/trigger", response_model=SyncTriggerResponse)
def trigger_sync(
    req: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a sync for a marketplace account. Runs in background."""
    account = db.get(MarketplaceAccount, req.marketplace_account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Marketplace account not found")
    if current_user.seller_id != account.seller_id:
        raise HTTPException(status_code=403, detail="Not your marketplace account")

    # Create a placeholder sync run so we can return the ID immediately
    sync_run = SyncRun(
        marketplace_account_id=req.marketplace_account_id,
        sync_type=req.sync_type,
        status="queued",
    )
    db.add(sync_run)
    db.commit()
    db.refresh(sync_run)

    background_tasks.add_task(_run_sync_background, req.marketplace_account_id, req.sync_type)
    return SyncTriggerResponse(sync_run_id=sync_run.id, message="Sync started in background")


@router.get("/runs", response_model=list[SyncRunResponse])
def list_sync_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List sync runs for the current user's marketplace accounts."""
    if not current_user.seller_id:
        return []
    account_ids = [
        a.id for a in db.query(MarketplaceAccount.id)
        .filter(MarketplaceAccount.seller_id == current_user.seller_id)
        .all()
    ]
    if not account_ids:
        return []
    runs = (
        db.query(SyncRun)
        .filter(SyncRun.marketplace_account_id.in_(account_ids))
        .order_by(SyncRun.started_at.desc())
        .limit(50)
        .all()
    )
    return runs


@router.get("/runs/{run_id}", response_model=SyncRunResponse)
def get_sync_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single sync run detail."""
    sync_run = db.get(SyncRun, run_id)
    if not sync_run:
        raise HTTPException(status_code=404, detail="Sync run not found")
    account = db.get(MarketplaceAccount, sync_run.marketplace_account_id)
    if not account or account.seller_id != current_user.seller_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return sync_run


@router.post("/seed-demo", response_model=SeedDemoResponse)
def seed_demo(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a demo seller + marketplace account and trigger mock sync.

    Designed for hackathon demo — populates realistic Indian e-commerce data.
    """
    # Reuse or create seller for current user
    if current_user.seller_id:
        seller = db.get(Seller, current_user.seller_id)
    else:
        seller = Seller(
            business_name="Edgecraft Demo Store",
            business_type="Proprietorship",
            primary_category="Home & Kitchen",
            gst_number="27AABCU9603R1ZP",
            city="Mumbai",
            state="Maharashtra",
            onboarding_completed=True,
        )
        db.add(seller)
        db.flush()
        current_user.seller_id = seller.id

    # Create or reuse Amazon marketplace account
    account = (
        db.query(MarketplaceAccount)
        .filter_by(seller_id=seller.id, marketplace="amazon")
        .first()
    )
    if not account:
        account = MarketplaceAccount(
            seller_id=seller.id,
            marketplace="amazon",
            status="connected",
        )
        db.add(account)
        db.flush()
    else:
        account.status = "connected"

    db.commit()
    db.refresh(account)

    # Run sync synchronously for demo (fast with mock data)
    sync_run = run_sync(db, account.id, sync_type="full")

    return SeedDemoResponse(
        seller_id=seller.id,
        marketplace_account_id=account.id,
        sync_run_id=sync_run.id,
        message=f"Demo data seeded: {sync_run.records_upserted} records upserted",
    )
