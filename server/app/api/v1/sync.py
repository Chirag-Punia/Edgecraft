"""Sync API endpoints — trigger syncs, view run history, seed demo data."""
import logging
from types import SimpleNamespace

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from boto3.dynamodb.conditions import Key, Attr

from app.core.dependencies import get_current_user
from app.db.session import SessionLocal, get_db
from app.dynamo.helpers import query_all, from_dynamo_item, to_dynamo_item, now_iso, query_by_account_ids, batch_delete_items
from app.enums import Marketplace, AccountStatus, SyncRunStatus, SyncType
from app.schemas.sync import (
    SyncTriggerRequest, SyncRunResponse, SyncTriggerResponse,
    SeedDemoResponse, UnseedResponse, DemoStatusResponse,
)
from app.services.sync_worker import run_sync

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["sync"])


def _run_sync_background(marketplace_account_id: int, sync_type: SyncType, force_mock: bool = False):
    """Background task wrapper — uses its own DB session."""
    db = SessionLocal()
    run_sync(db, marketplace_account_id, sync_type, force_mock=force_mock)


@router.post("/trigger", response_model=SyncTriggerResponse)
def trigger_sync(
    req: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Trigger a sync for a marketplace account. Runs in background."""
    accounts_table = db.get_table("marketplace_accounts")
    response = accounts_table.get_item(Key={"id": req.marketplace_account_id})
    account = response.get("Item")
    if not account:
        raise HTTPException(status_code=404, detail="Marketplace account not found")
    account = from_dynamo_item(account)
    if current_user.seller_id != account.get("seller_id"):
        raise HTTPException(status_code=403, detail="Not your marketplace account")

    background_tasks.add_task(_run_sync_background, req.marketplace_account_id, req.sync_type)
    return SyncTriggerResponse(sync_run_id=0, message="Sync started in background")


@router.get("/runs", response_model=list[SyncRunResponse])
def list_sync_runs(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List sync runs for the current user's marketplace accounts."""
    if not current_user.seller_id:
        return []

    # Get marketplace account IDs for this seller
    accounts_table = db.get_table("marketplace_accounts")
    accounts = query_all(accounts_table, IndexName="seller-index",
                         KeyConditionExpression=Key("seller_id").eq(current_user.seller_id))
    account_ids = [a["id"] for a in accounts]
    if not account_ids:
        return []

    # Query sync runs for each account
    sync_runs_table = db.get_table("sync_runs")
    all_runs = []
    for aid in account_ids:
        runs = query_all(sync_runs_table, IndexName="account-index",
                         KeyConditionExpression=Key("marketplace_account_id").eq(aid))
        all_runs.extend(runs)

    # Sort by started_at descending, limit to 50
    all_runs.sort(key=lambda r: r.get("started_at", ""), reverse=True)
    all_runs = all_runs[:50]

    return [
        SyncRunResponse(
            id=r["id"],
            marketplace_account_id=r["marketplace_account_id"],
            sync_type=r.get("sync_type", SyncType.FULL.value),
            status=r.get("status", SyncRunStatus.QUEUED.value),
            started_at=r.get("started_at"),
            completed_at=r.get("completed_at"),
            records_fetched=r.get("records_fetched", 0),
            records_upserted=r.get("records_upserted", 0),
            error_log=r.get("error_log"),
        )
        for r in all_runs
    ]


@router.get("/runs/{run_id}", response_model=SyncRunResponse)
def get_sync_run(
    run_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a single sync run detail."""
    sync_runs_table = db.get_table("sync_runs")
    response = sync_runs_table.get_item(Key={"id": run_id})
    item = response.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Sync run not found")
    run = from_dynamo_item(item)

    # Verify ownership
    accounts_table = db.get_table("marketplace_accounts")
    acct_response = accounts_table.get_item(Key={"id": run["marketplace_account_id"]})
    acct_item = acct_response.get("Item")
    if not acct_item:
        raise HTTPException(status_code=403, detail="Not authorized")
    account = from_dynamo_item(acct_item)
    if account.get("seller_id") != current_user.seller_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return SyncRunResponse(
        id=run["id"],
        marketplace_account_id=run["marketplace_account_id"],
        sync_type=run.get("sync_type", SyncType.FULL.value),
        status=run.get("status", SyncRunStatus.QUEUED.value),
        started_at=run.get("started_at"),
        completed_at=run.get("completed_at"),
        records_fetched=run.get("records_fetched", 0),
        records_upserted=run.get("records_upserted", 0),
        error_log=run.get("error_log"),
    )


@router.post("/seed-demo", response_model=SeedDemoResponse)
def seed_demo(
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a demo seller + marketplace account and trigger mock sync.

    Designed for hackathon demo — populates realistic Indian e-commerce data.
    Runs sync in background; frontend polls demo-status for completion.
    """
    sellers_table = db.get_table("sellers")
    accounts_table = db.get_table("marketplace_accounts")
    users_table = db.get_table("users")

    # Reuse or create seller for current user
    if current_user.seller_id:
        response = sellers_table.get_item(Key={"id": current_user.seller_id})
        seller = from_dynamo_item(response.get("Item", {}))
    else:
        seller_id = db.next_id("sellers")
        now = now_iso()
        seller = {
            "id": seller_id,
            "business_name": "Edgecraft Demo Store",
            "business_type": "Proprietorship",
            "primary_category": "Home & Kitchen",
            "gst_number": "27AABCU9603R1ZP",
            "city": "Mumbai",
            "state": "Maharashtra",
            "onboarding_completed": True,
            "created_at": now,
            "updated_at": now,
        }
        sellers_table.put_item(Item=to_dynamo_item(seller))

        # Update user's seller_id
        users_table.update_item(
            Key={"id": current_user.id},
            UpdateExpression="SET seller_id = :sid",
            ExpressionAttributeValues={":sid": seller_id},
        )

    # Check for existing Amazon marketplace account
    seller_accounts = query_all(accounts_table, IndexName="seller-index",
                                KeyConditionExpression=Key("seller_id").eq(seller["id"]))
    account = None
    for a in seller_accounts:
        if a.get("marketplace") == Marketplace.AMAZON.value:
            account = a
            break

    if not account:
        account_id = db.next_id("marketplace_accounts")
        now = now_iso()
        account = {
            "id": account_id,
            "seller_id": seller["id"],
            "marketplace": Marketplace.AMAZON.value,
            "status": AccountStatus.CONNECTED.value,
            "is_demo_data": True,
            "created_at": now,
            "updated_at": now,
        }
        accounts_table.put_item(Item=to_dynamo_item(account))
    else:
        # Update existing account
        accounts_table.update_item(
            Key={"id": account["id"]},
            UpdateExpression="SET #s = :status, is_demo_data = :demo, last_sync_at = :null_val, updated_at = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": AccountStatus.CONNECTED.value,
                ":demo": True,
                ":null_val": None,
                ":now": now_iso(),
            },
        )
        account["status"] = AccountStatus.CONNECTED.value
        account["is_demo_data"] = True
        account["last_sync_at"] = None

    # Run sync in background (frontend polls demo-status for completion)
    background_tasks.add_task(_run_sync_background, account["id"], SyncType.FULL, force_mock=True)

    return SeedDemoResponse(
        seller_id=seller["id"],
        marketplace_account_id=account["id"],
        sync_run_id=0,
        message="Demo data seeding started",
    )


@router.post("/unseed", response_model=UnseedResponse)
def unseed_demo(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Remove all demo data for the current user's seller."""
    if not current_user.seller_id:
        raise HTTPException(status_code=400, detail="No seller linked to this user")

    # Find demo marketplace accounts
    accounts_table = db.get_table("marketplace_accounts")
    seller_accounts = query_all(accounts_table, IndexName="seller-index",
                                KeyConditionExpression=Key("seller_id").eq(current_user.seller_id))
    demo_accounts = [a for a in seller_accounts if a.get("is_demo_data")]

    if not demo_accounts:
        return UnseedResponse(message="No demo data found", records_deleted=0)

    account_ids = [a["id"] for a in demo_accounts]
    total = 0

    def _collect_keys(table, account_ids, key_extractor, index_name=None):
        """Collect keys from all accounts for batch deletion."""
        keys = []
        for aid in account_ids:
            kwargs = {"KeyConditionExpression": Key("marketplace_account_id").eq(aid)}
            if index_name:
                kwargs["IndexName"] = index_name
            items = query_all(table, **kwargs)
            keys.extend(key_extractor(item) for item in items)
        return keys

    # Delete pricing_recommendations
    pr_table = db.get_table("pricing_recommendations")
    pr_keys = _collect_keys(pr_table, account_ids,
                            lambda i: {"marketplace_account_id": i["marketplace_account_id"], "asin_date": i["asin_date"]})
    batch_delete_items(pr_table, pr_keys)
    total += len(pr_keys)

    # Delete demand_forecasts
    df_table = db.get_table("demand_forecasts")
    df_keys = _collect_keys(df_table, account_ids,
                            lambda i: {"marketplace_account_id": i["marketplace_account_id"], "asin_date_horizon": i["asin_date_horizon"]})
    batch_delete_items(df_table, df_keys)
    total += len(df_keys)

    # Delete review_insights
    ri_table = db.get_table("review_insights")
    ri_keys = _collect_keys(ri_table, account_ids,
                            lambda i: {"marketplace_account_id": i["marketplace_account_id"], "asin_date": i["asin_date"]})
    batch_delete_items(ri_table, ri_keys)
    total += len(ri_keys)

    # Delete customer_reviews
    cr_table = db.get_table("customer_reviews")
    cr_keys = _collect_keys(cr_table, account_ids,
                            lambda i: {"marketplace_account_id": i["marketplace_account_id"], "external_review_id": i["external_review_id"]})
    batch_delete_items(cr_table, cr_keys)
    total += len(cr_keys)

    # Delete order_items
    oi_table = db.get_table("order_items")
    oi_keys = _collect_keys(oi_table, account_ids, lambda i: {"id": i["id"]}, index_name="account-index")
    batch_delete_items(oi_table, oi_keys)
    total += len(oi_keys)

    # Delete orders
    orders_table = db.get_table("orders")
    ord_keys = _collect_keys(orders_table, account_ids, lambda i: {"id": i["id"]}, index_name="account-date-index")
    batch_delete_items(orders_table, ord_keys)
    total += len(ord_keys)

    # Delete inventory_snapshots
    inv_table = db.get_table("inventory_snapshots")
    inv_keys = _collect_keys(inv_table, account_ids,
                             lambda i: {"marketplace_account_id": i["marketplace_account_id"], "sku_date": i["sku_date"]})
    batch_delete_items(inv_table, inv_keys)
    total += len(inv_keys)

    # Delete price_snapshots
    ps_table = db.get_table("price_snapshots")
    ps_keys = _collect_keys(ps_table, account_ids,
                            lambda i: {"marketplace_account_id": i["marketplace_account_id"], "asin_date": i["asin_date"]})
    batch_delete_items(ps_table, ps_keys)
    total += len(ps_keys)

    # Delete listing_map
    lm_table = db.get_table("listing_map")
    lm_keys = _collect_keys(lm_table, account_ids,
                            lambda i: {"marketplace_account_id": i["marketplace_account_id"], "marketplace_sku": i["marketplace_sku"]})
    batch_delete_items(lm_table, lm_keys)
    total += len(lm_keys)

    # Delete product_master
    pm_table = db.get_table("product_master")
    pm_items = query_all(pm_table, KeyConditionExpression=Key("seller_id").eq(current_user.seller_id))
    pm_keys = [{"seller_id": i["seller_id"], "id": i["id"]} for i in pm_items]
    batch_delete_items(pm_table, pm_keys)
    total += len(pm_keys)

    # Delete sync_runs
    sr_table = db.get_table("sync_runs")
    sr_keys = _collect_keys(sr_table, account_ids, lambda i: {"id": i["id"]}, index_name="account-index")
    batch_delete_items(sr_table, sr_keys)
    total += len(sr_keys)

    # Mark demo accounts as disconnected
    for account in demo_accounts:
        accounts_table.update_item(
            Key={"id": account["id"]},
            UpdateExpression="SET #s = :status REMOVE credentials_encrypted",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":status": AccountStatus.DISCONNECTED.value},
        )

    logger.info("Unseeded %d records for seller %d", total, current_user.seller_id)
    return UnseedResponse(message=f"Demo data removed: {total} records deleted", records_deleted=total)


@router.get("/demo-status", response_model=DemoStatusResponse)
def demo_status(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Check if current user has active demo data."""
    if not current_user.seller_id:
        return DemoStatusResponse(is_seeded=False)

    # Find demo marketplace accounts
    accounts_table = db.get_table("marketplace_accounts")
    seller_accounts = query_all(accounts_table, IndexName="seller-index",
                                KeyConditionExpression=Key("seller_id").eq(current_user.seller_id))
    demo_accounts = [a for a in seller_accounts if a.get("is_demo_data")]

    if not demo_accounts:
        return DemoStatusResponse(is_seeded=False, is_seeding=False)

    # Check if any demo account has a completed or running sync run
    sync_runs_table = db.get_table("sync_runs")
    has_running = False
    for account in demo_accounts:
        runs = query_all(sync_runs_table, IndexName="account-index",
                         KeyConditionExpression=Key("marketplace_account_id").eq(account["id"]))
        for run in runs:
            if run.get("status") == SyncRunStatus.COMPLETED.value:
                return DemoStatusResponse(is_seeded=True, is_seeding=False)
            if run.get("status") in (SyncRunStatus.RUNNING.value, SyncRunStatus.QUEUED.value):
                has_running = True

    return DemoStatusResponse(is_seeded=False, is_seeding=has_running)
