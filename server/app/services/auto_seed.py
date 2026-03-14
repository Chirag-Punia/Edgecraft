"""Auto-seed demo data for newly onboarded users."""
import logging
from types import SimpleNamespace

from boto3.dynamodb.conditions import Key, Attr

from app.db.session import SessionLocal
from app.enums import Marketplace, AccountStatus, SyncRunStatus, SyncType
from app.dynamo.helpers import to_dynamo_item, from_dynamo_item, query_all, now_iso
from app.services.sync_worker import run_sync

logger = logging.getLogger(__name__)


def auto_seed_for_user(user_id: int):
    """Background task: create demo marketplace account and run mock sync."""
    db = SessionLocal()
    try:
        # Get user
        users_table = db.get_table("users")
        resp = users_table.get_item(Key={"id": user_id})
        if "Item" not in resp:
            logger.warning("auto_seed: user %s not found, skipping", user_id)
            return
        user = from_dynamo_item(resp["Item"])

        seller_id = user.get("seller_id")
        if not seller_id:
            logger.warning("auto_seed: user %s has no seller_id, skipping", user_id)
            return

        acct_table = db.get_table("marketplace_accounts")
        sync_table = db.get_table("sync_runs")

        # Idempotency: check if demo account with a completed or running sync exists
        demo_accounts = query_all(
            acct_table,
            IndexName="seller-index",
            KeyConditionExpression=Key("seller_id").eq(int(seller_id)),
            FilterExpression=Attr("is_demo_data").eq(True),
        )

        for demo_acct in demo_accounts:
            # Check if this demo account has a completed or running sync
            syncs = query_all(
                sync_table,
                IndexName="account-index",
                KeyConditionExpression=Key("marketplace_account_id").eq(demo_acct["id"]),
                FilterExpression=Attr("status").is_in([SyncRunStatus.COMPLETED.value, SyncRunStatus.RUNNING.value]),
            )
            if syncs:
                logger.info("auto_seed: demo data already exists for seller %s, skipping", seller_id)
                return

        # Create or reuse Amazon marketplace account
        seller_accounts = query_all(
            acct_table,
            IndexName="seller-index",
            KeyConditionExpression=Key("seller_id").eq(int(seller_id)),
            FilterExpression=Attr("marketplace").eq(Marketplace.AMAZON.value),
        )

        account_id = None
        if seller_accounts:
            account = seller_accounts[0]
            if not account.get("is_demo_data", False):
                # Real account exists via OAuth -- don't overwrite it
                logger.info("auto_seed: real Amazon account exists for seller %s, skipping", seller_id)
                return
            # Reuse existing demo account
            account_id = account["id"]
            acct_table.update_item(
                Key={"id": account_id},
                UpdateExpression="SET #s = :s, last_sync_at = :ls, updated_at = :ua",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":s": AccountStatus.CONNECTED.value,
                    ":ls": None,
                    ":ua": now_iso(),
                },
            )
        else:
            # Create new demo marketplace account
            account_id = db.next_id("marketplace_accounts")
            now = now_iso()
            acct_item = {
                "id": account_id,
                "seller_id": int(seller_id),
                "marketplace": Marketplace.AMAZON.value,
                "status": AccountStatus.CONNECTED.value,
                "is_demo_data": True,
                "created_at": now,
                "updated_at": now,
            }
            acct_table.put_item(Item=to_dynamo_item(acct_item))

        logger.info("auto_seed: running mock sync for user %s, account %s", user_id, account_id)
        run_sync(db, account_id, sync_type=SyncType.FULL, force_mock=True)

    except Exception:
        logger.exception("auto_seed failed for user %s", user_id)
