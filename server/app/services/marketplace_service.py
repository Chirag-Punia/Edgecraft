"""Marketplace account CRUD operations using DynamoDB."""
import json
import logging
from types import SimpleNamespace

from fastapi import HTTPException, status
from boto3.dynamodb.conditions import Key, Attr

from app.enums import Marketplace, AccountStatus
from app.dynamo.helpers import to_dynamo_item, from_dynamo_item, query_all, now_iso

logger = logging.getLogger(__name__)


def create_marketplace(db, seller_id: int, marketplace: Marketplace, credentials: dict | None):
    """Create a new marketplace account for a seller."""
    table = db.get_table("marketplace_accounts")

    marketplace_val = marketplace.value if hasattr(marketplace, "value") else marketplace

    # Check existing via seller-index GSI
    existing = query_all(
        table,
        IndexName="seller-index",
        KeyConditionExpression=Key("seller_id").eq(int(seller_id)),
        FilterExpression=Attr("marketplace").eq(marketplace_val),
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{marketplace_val} already connected",
        )

    account_id = db.next_id("marketplace_accounts")
    now = now_iso()
    item = {
        "id": account_id,
        "seller_id": int(seller_id),
        "marketplace": marketplace_val,
        "status": AccountStatus.CONNECTED.value,
        "credentials_encrypted": json.dumps(credentials) if credentials else None,
        "is_demo_data": False,
        "last_sync_at": None,
        "created_at": now,
        "updated_at": now,
    }
    table.put_item(Item=to_dynamo_item(item))
    item.setdefault("last_sync_at", None)
    return SimpleNamespace(**item)


def list_marketplaces(db, seller_id: int, include_demo: bool = False):
    """List all marketplace accounts for a seller."""
    table = db.get_table("marketplace_accounts")

    filter_expr = None
    if not include_demo:
        filter_expr = Attr("is_demo_data").ne(True)

    query_kwargs = {
        "IndexName": "seller-index",
        "KeyConditionExpression": Key("seller_id").eq(int(seller_id)),
    }
    if filter_expr is not None:
        query_kwargs["FilterExpression"] = filter_expr

    accounts = query_all(table, **query_kwargs)

    results = []
    for a in accounts:
        a.setdefault("last_sync_at", None)
        results.append(SimpleNamespace(**a))
    return results


def connect_amazon_oauth(db, seller_id: int, selling_partner_id: str, refresh_token: str):
    """Create or update an Amazon marketplace account after successful OAuth."""
    logger.info(
        "[Marketplace] connect_amazon_oauth called: seller_id=%s, selling_partner_id=%s",
        seller_id, selling_partner_id,
    )
    table = db.get_table("marketplace_accounts")
    creds = json.dumps({"refresh_token": refresh_token, "selling_partner_id": selling_partner_id})

    # Prefer a real account; ignore demo accounts to avoid lock conflicts with auto-seed syncs.
    real_accounts = query_all(
        table,
        IndexName="seller-index",
        KeyConditionExpression=Key("seller_id").eq(int(seller_id)),
        FilterExpression=(
            Attr("marketplace").eq(Marketplace.AMAZON.value) &
            Attr("is_demo_data").ne(True)
        ),
    )

    now = now_iso()

    if real_accounts:
        existing = real_accounts[0]
        logger.info(
            "[Marketplace] Existing real Amazon account found: id=%s, old_status=%s -- updating credentials",
            existing["id"], existing.get("status"),
        )
        table.update_item(
            Key={"id": existing["id"]},
            UpdateExpression="SET credentials_encrypted = :c, #s = :s, updated_at = :ua",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":c": creds,
                ":s": AccountStatus.CONNECTED.value,
                ":ua": now,
            },
        )
        # Re-fetch to return updated data
        resp = table.get_item(Key={"id": existing["id"]})
        account_data = from_dynamo_item(resp["Item"])
        account_data.setdefault("last_sync_at", None)
        logger.info("[Marketplace] Amazon account saved: id=%s, status=%s", account_data["id"], account_data.get("status"))
        return SimpleNamespace(**account_data)
    else:
        logger.info("[Marketplace] No real Amazon account -- creating new for seller_id=%s", seller_id)
        account_id = db.next_id("marketplace_accounts")
        item = {
            "id": account_id,
            "seller_id": int(seller_id),
            "marketplace": Marketplace.AMAZON.value,
            "status": AccountStatus.CONNECTED.value,
            "credentials_encrypted": creds,
            "is_demo_data": False,
            "last_sync_at": None,
            "created_at": now,
            "updated_at": now,
        }
        table.put_item(Item=to_dynamo_item(item))
        item.setdefault("last_sync_at", None)
        account = SimpleNamespace(**item)
        logger.info("[Marketplace] Amazon account saved: id=%s, status=%s", account.id, account.status)
        return account


def delete_marketplace(db, seller_id: int, marketplace_id: int) -> None:
    """Delete a marketplace account."""
    table = db.get_table("marketplace_accounts")

    resp = table.get_item(Key={"id": marketplace_id})
    if "Item" not in resp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marketplace account not found",
        )

    account = from_dynamo_item(resp["Item"])
    if account.get("seller_id") != int(seller_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marketplace account not found",
        )

    table.delete_item(Key={"id": marketplace_id})
