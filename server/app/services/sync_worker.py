"""ETL sync worker — fetches marketplace data, normalizes, and upserts into MySQL."""
import json
import logging
import os
from datetime import datetime, timedelta, date
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.config import get_settings
from app.models.sync_run import SyncRun
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.inventory_snapshot import InventorySnapshot
from app.models.listing_map import ListingMap
from app.models.price_snapshot import PriceSnapshot
from app.models.marketplace_account import MarketplaceAccount
from app.services.mock_amazon_data import MockAmazonConnector
from app.services.amazon_connector import AmazonConnector

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_connector(marketplace_account: MarketplaceAccount):
    """Pick mock or real connector based on config."""
    if settings.USE_MOCK_DATA:
        return MockAmazonConnector()
    creds = json.loads(marketplace_account.credentials_encrypted or "{}")
    # Fall back to global config if per-account creds are missing
    if not creds.get("refresh_token"):
        creds = {
            "refresh_token": settings.SP_API_REFRESH_TOKEN,
            "lwa_app_id": settings.SP_API_LWA_APP_ID,
            "lwa_client_secret": settings.SP_API_LWA_CLIENT_SECRET,
            "aws_access_key": settings.SP_API_AWS_ACCESS_KEY,
            "aws_secret_key": settings.SP_API_AWS_SECRET_KEY,
            "role_arn": settings.SP_API_ROLE_ARN,
        }
    return AmazonConnector(creds)


def _save_raw_dump(seller_id: int, entity: str, run_id: int, data: list | dict):
    """Save raw API response to disk for debugging/audit."""
    dir_path = os.path.join(
        settings.RAW_DUMP_DIR, str(seller_id), "amazon", entity,
        date.today().isoformat(),
    )
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, f"{run_id}.json")
    with open(file_path, "w") as f:
        json.dump(data, f, default=str, indent=2)


def _upsert(db: Session, model, values: dict, update_fields: list[str]):
    """MySQL upsert using INSERT ... ON DUPLICATE KEY UPDATE."""
    stmt = mysql_insert(model).values(**values)
    update_dict = {field: getattr(stmt.inserted, field) for field in update_fields}
    stmt = stmt.on_duplicate_key_update(**update_dict)
    db.execute(stmt)


def _parse_amount(amount_obj) -> Decimal:
    """Extract amount from SP-API money object or raw value."""
    if isinstance(amount_obj, dict):
        return Decimal(str(amount_obj.get("Amount", "0")))
    return Decimal(str(amount_obj or "0"))


def run_sync(db: Session, marketplace_account_id: int, sync_type: str = "full") -> SyncRun:
    """Run a full ETL sync for a marketplace account."""
    account = db.get(MarketplaceAccount, marketplace_account_id)
    if not account:
        raise ValueError(f"MarketplaceAccount {marketplace_account_id} not found")

    sync_run = SyncRun(
        marketplace_account_id=marketplace_account_id,
        sync_type=sync_type,
        status="running",
    )
    db.add(sync_run)
    db.flush()

    total_fetched = 0
    total_upserted = 0

    try:
        connector = _get_connector(account)

        # --- Sync Orders ---
        created_after = account.last_sync_at or (datetime.utcnow() - timedelta(days=30))
        raw_orders = connector.get_orders(created_after=created_after)
        _save_raw_dump(account.seller_id, "orders", sync_run.id, raw_orders)
        total_fetched += len(raw_orders)

        order_id_map = {}  # external_order_id -> db order id

        for raw_order in raw_orders:
            ext_id = raw_order["AmazonOrderId"]
            order_date_str = raw_order.get("PurchaseDate", "")
            try:
                order_date = datetime.fromisoformat(order_date_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                order_date = datetime.utcnow()

            total_amount = _parse_amount(raw_order.get("OrderTotal", {}))
            shipping_amount = _parse_amount(raw_order.get("ShippingPrice", 0))
            addr = raw_order.get("ShippingAddress", {})

            order_vals = {
                "marketplace_account_id": marketplace_account_id,
                "external_order_id": ext_id,
                "marketplace": "amazon",
                "status": raw_order.get("OrderStatus", "Unknown"),
                "order_date": order_date,
                "fulfillment_channel": raw_order.get("FulfillmentChannel"),
                "currency": raw_order.get("OrderTotal", {}).get("CurrencyCode", "INR") if isinstance(raw_order.get("OrderTotal"), dict) else "INR",
                "total_amount": total_amount,
                "shipping_amount": shipping_amount,
                "ship_city": addr.get("City"),
                "ship_state": addr.get("StateOrRegion"),
                "raw_payload": json.dumps(raw_order, default=str),
            }
            _upsert(db, Order, order_vals, [
                "status", "total_amount", "shipping_amount", "ship_city", "ship_state", "raw_payload",
            ])
            total_upserted += 1

            # Retrieve the order's DB id for order_items FK
            existing = db.query(Order).filter_by(
                marketplace_account_id=marketplace_account_id,
                external_order_id=ext_id,
            ).first()
            if existing:
                order_id_map[ext_id] = existing.id

        db.flush()

        # --- Sync Order Items ---
        for raw_order in raw_orders:
            ext_id = raw_order["AmazonOrderId"]
            db_order_id = order_id_map.get(ext_id)
            if not db_order_id:
                continue

            mock_items = raw_order.get("_mock_items")
            raw_items = connector.get_order_items(ext_id, _mock_items=mock_items)
            total_fetched += len(raw_items)

            for raw_item in raw_items:
                item_vals = {
                    "order_id": db_order_id,
                    "marketplace_account_id": marketplace_account_id,
                    "external_order_item_id": raw_item["OrderItemId"],
                    "asin": raw_item.get("ASIN"),
                    "seller_sku": raw_item.get("SellerSKU"),
                    "title": raw_item.get("Title"),
                    "quantity_ordered": raw_item.get("QuantityOrdered", 1),
                    "quantity_shipped": raw_item.get("QuantityShipped", 0),
                    "unit_price": _parse_amount(raw_item.get("ItemPrice", {})),
                    "item_tax": _parse_amount(raw_item.get("ItemTax", {})),
                    "item_discount": _parse_amount(raw_item.get("PromotionDiscount", {})),
                }
                _upsert(db, OrderItem, item_vals, [
                    "quantity_ordered", "quantity_shipped", "unit_price", "item_tax", "item_discount",
                ])
                total_upserted += 1

        db.flush()

        # --- Sync Inventory ---
        raw_inventory = connector.get_inventory_summaries()
        _save_raw_dump(account.seller_id, "inventory", sync_run.id, raw_inventory)
        total_fetched += len(raw_inventory)
        today = date.today()

        known_asins = set()

        for item in raw_inventory:
            details = item.get("inventoryDetails", {})
            reserved = details.get("reservedQuantity", {})
            unfulfillable = details.get("unfulfillableQuantity", {})

            inv_vals = {
                "marketplace_account_id": marketplace_account_id,
                "seller_sku": item["sellerSku"],
                "asin": item.get("asin"),
                "fnsku": item.get("fnSku"),
                "fulfillable_quantity": details.get("fulfillableQuantity", 0),
                "inbound_quantity": details.get("inboundWorkingQuantity", 0) + details.get("inboundShippedQuantity", 0),
                "reserved_quantity": reserved.get("totalReservedQuantity", 0) if isinstance(reserved, dict) else int(reserved or 0),
                "unfulfillable_quantity": unfulfillable.get("totalUnfulfillableQuantity", 0) if isinstance(unfulfillable, dict) else int(unfulfillable or 0),
                "total_quantity": item.get("totalQuantity", 0),
                "snapshot_date": today,
            }
            _upsert(db, InventorySnapshot, inv_vals, [
                "fulfillable_quantity", "inbound_quantity", "reserved_quantity",
                "unfulfillable_quantity", "total_quantity",
            ])
            total_upserted += 1

            # Build listing map from inventory data
            known_asins.add(item.get("asin"))
            listing_vals = {
                "marketplace_account_id": marketplace_account_id,
                "marketplace_sku": item["sellerSku"],
                "asin": item.get("asin"),
                "fnsku": item.get("fnSku"),
                "listing_title": item.get("productName"),
                "listing_status": "active",
            }
            _upsert(db, ListingMap, listing_vals, [
                "asin", "fnsku", "listing_title", "listing_status",
            ])
            total_upserted += 1

        db.flush()

        # --- Sync Pricing ---
        asin_list = [a for a in known_asins if a]
        if asin_list:
            raw_pricing = connector.get_competitive_pricing(asin_list)
            _save_raw_dump(account.seller_id, "pricing", sync_run.id, raw_pricing)
            total_fetched += len(raw_pricing)

            for item in raw_pricing:
                price_vals = {
                    "marketplace_account_id": marketplace_account_id,
                    "asin": item["ASIN"],
                    "seller_sku": item.get("SellerSKU"),
                    "your_price": Decimal(str(item["YourPrice"])) if item.get("YourPrice") else None,
                    "landed_price": Decimal(str(item["LandedPrice"])) if item.get("LandedPrice") else None,
                    "buybox_price": Decimal(str(item["BuyBoxPrice"])) if item.get("BuyBoxPrice") else None,
                    "lowest_price": Decimal(str(item["LowestPrice"])) if item.get("LowestPrice") else None,
                    "is_buybox_winner": item.get("IsBuyBoxWinner", False),
                    "snapshot_date": today,
                }
                _upsert(db, PriceSnapshot, price_vals, [
                    "your_price", "landed_price", "buybox_price", "lowest_price", "is_buybox_winner",
                ])
                total_upserted += 1

        db.flush()

        # Update account last_sync_at
        account.last_sync_at = datetime.utcnow()
        sync_run.status = "completed"
        sync_run.records_fetched = total_fetched
        sync_run.records_upserted = total_upserted
        sync_run.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Sync completed: account={marketplace_account_id}, fetched={total_fetched}, upserted={total_upserted}")

    except Exception as e:
        logger.exception(f"Sync failed for account {marketplace_account_id}")
        sync_run.status = "failed"
        sync_run.error_log = str(e)[:2000]
        sync_run.completed_at = datetime.utcnow()
        db.commit()

    return sync_run
