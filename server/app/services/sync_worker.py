"""ETL sync worker — fetches marketplace data, normalizes, and upserts into MySQL."""
import json
import logging
import os
import random
from datetime import datetime, timedelta, date
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.config import get_settings
from app.enums import Marketplace, SyncRunStatus, SyncType, ListingStatus
from app.models.sync_run import SyncRun
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.inventory_snapshot import InventorySnapshot
from app.models.listing_map import ListingMap
from app.models.price_snapshot import PriceSnapshot
from app.models.product_master import ProductMaster
from app.models.marketplace_account import MarketplaceAccount
from app.services.mock_amazon_data import MockAmazonConnector, PRODUCTS
from app.services.amazon_connector import AmazonConnector
from app.services.mock_reviews_data import generate_mock_reviews
from app.models.customer_review import CustomerReview

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_connector(marketplace_account: MarketplaceAccount, force_mock: bool = False):
    """Pick mock or real connector based on config."""
    if force_mock or settings.USE_MOCK_DATA:
        logger.info("[Sync] Using MockAmazonConnector")
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
    logger.info("[Sync] Using real AmazonConnector")
    return AmazonConnector(creds)


def _save_raw_dump(seller_id: int, entity: str, run_id: int, data: list | dict):
    """Save raw API response to disk for debugging/audit."""
    try:
        dir_path = os.path.join(
            settings.RAW_DUMP_DIR, str(seller_id), Marketplace.AMAZON, entity,
            date.today().isoformat(),
        )
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, f"{run_id}.json")
        with open(file_path, "w") as f:
            json.dump(data, f, default=str, indent=2)
    except OSError:
        logger.warning("Cannot write raw dump (read-only filesystem), skipping")


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


def _seed_historical_inventory(db: Session, marketplace_account_id: int):
    """Generate 30 days of historical inventory snapshots for demo mode."""
    rng = random.Random(42)
    today = date.today()

    restock_products = {PRODUCTS[i]["sku"] for i in [2, 7, 11]}
    stockout_products = {PRODUCTS[i]["sku"] for i in [4, 9, 14]}

    count = 0
    for product in PRODUCTS:
        sku = product["sku"]
        asin = product["asin"]
        fnsku = f"X00{asin[3:]}"

        base_stock = rng.randint(80, 200)
        daily_depletion = rng.uniform(1.5, 6.0)

        for day_offset in range(30, 0, -1):
            snap_date = today - timedelta(days=day_offset)
            days_elapsed = 30 - day_offset

            stock = base_stock - int(daily_depletion * days_elapsed)

            if sku in restock_products and days_elapsed >= 15:
                stock += rng.randint(50, 100)

            if sku in stockout_products:
                stock = max(0, base_stock - int(daily_depletion * 2.5 * days_elapsed))

            stock = max(0, stock)
            fulfillable = stock
            inbound = rng.randint(0, 15) if stock < 30 else rng.randint(0, 5)
            reserved = rng.randint(0, min(stock, 10))
            unfulfillable = rng.randint(0, 2)
            total = fulfillable + inbound + reserved + unfulfillable

            inv_vals = {
                "marketplace_account_id": marketplace_account_id,
                "seller_sku": sku,
                "asin": asin,
                "fnsku": fnsku,
                "fulfillable_quantity": fulfillable,
                "inbound_quantity": inbound,
                "reserved_quantity": reserved,
                "unfulfillable_quantity": unfulfillable,
                "total_quantity": total,
                "snapshot_date": snap_date,
            }
            _upsert(db, InventorySnapshot, inv_vals, [
                "fulfillable_quantity", "inbound_quantity", "reserved_quantity",
                "unfulfillable_quantity", "total_quantity",
            ])
            count += 1

    db.flush()
    logger.info("Seeded %d historical inventory snapshots", count)
    return count


def _seed_historical_prices(db: Session, marketplace_account_id: int):
    """Generate 30 days of historical price snapshots for demo mode."""
    rng = random.Random(42)
    today = date.today()

    buybox_losers = {PRODUCTS[i]["asin"] for i in [1, 5, 10, 15]}

    count = 0
    for product in PRODUCTS:
        asin = product["asin"]
        sku = product["sku"]
        base_price = float(product["price"])
        your_price = base_price

        for day_offset in range(30, 0, -1):
            snap_date = today - timedelta(days=day_offset)
            day_idx = 30 - day_offset

            if rng.random() < 0.08:
                your_price = base_price * rng.uniform(0.99, 1.01)
            else:
                your_price = base_price

            buybox_price = base_price * rng.uniform(0.95, 1.05)
            if asin in buybox_losers:
                buybox_price = base_price * (1.0 - 0.002 * day_idx) * rng.uniform(0.97, 1.01)

            lowest_price = base_price * rng.uniform(0.92, 1.0)
            is_winner = your_price <= buybox_price

            price_vals = {
                "marketplace_account_id": marketplace_account_id,
                "asin": asin,
                "seller_sku": sku,
                "your_price": Decimal(str(round(your_price, 2))),
                "landed_price": Decimal(str(round(your_price + rng.choice([0, 40, 60]), 2))),
                "buybox_price": Decimal(str(round(buybox_price, 2))),
                "lowest_price": Decimal(str(round(lowest_price, 2))),
                "is_buybox_winner": is_winner,
                "snapshot_date": snap_date,
            }
            _upsert(db, PriceSnapshot, price_vals, [
                "your_price", "landed_price", "buybox_price", "lowest_price", "is_buybox_winner",
            ])
            count += 1

    db.flush()
    logger.info("Seeded %d historical price snapshots", count)
    return count


def _seed_product_master(db: Session, seller_id: int, marketplace_account_id: int):
    """Seed ProductMaster records and link ListingMap entries for demo mode."""
    count = 0
    for product in PRODUCTS:
        existing = (
            db.query(ProductMaster)
            .filter_by(seller_id=seller_id, name=product["name"])
            .first()
        )
        if existing:
            existing.brand = product["brand"]
            existing.category = product["category"]
            pm = existing
        else:
            pm = ProductMaster(
                seller_id=seller_id,
                name=product["name"],
                brand=product["brand"],
                category=product["category"],
            )
            db.add(pm)
            db.flush()
            count += 1

        listing = (
            db.query(ListingMap)
            .filter_by(
                marketplace_account_id=marketplace_account_id,
                marketplace_sku=product["sku"],
            )
            .first()
        )
        if listing:
            listing.product_master_id = pm.id

    db.flush()
    logger.info("Seeded %d ProductMaster records and linked ListingMap", count)
    return count


def run_sync(db: Session, marketplace_account_id: int, sync_type: SyncType = SyncType.FULL, force_mock: bool = False) -> SyncRun:
    """Run a full ETL sync for a marketplace account."""
    account = db.get(MarketplaceAccount, marketplace_account_id)
    if not account:
        raise ValueError(f"MarketplaceAccount {marketplace_account_id} not found")

    sync_run = SyncRun(
        marketplace_account_id=marketplace_account_id,
        sync_type=sync_type,
        status=SyncRunStatus.RUNNING,
    )
    db.add(sync_run)
    db.flush()

    total_fetched = 0
    total_upserted = 0

    try:
        connector = _get_connector(account, force_mock=force_mock)

        # --- Sync Orders ---
        created_after = account.last_sync_at or (datetime.utcnow() - timedelta(days=180))
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
                "marketplace": Marketplace.AMAZON,
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
                "listing_status": ListingStatus.ACTIVE,
            }
            _upsert(db, ListingMap, listing_vals, [
                "asin", "fnsku", "listing_title", "listing_status",
            ])
            total_upserted += 1

        db.flush()

        # --- Seed historical inventory snapshots (demo mode) ---
        if force_mock:
            total_upserted += _seed_historical_inventory(db, marketplace_account_id)

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

        # --- Seed historical price snapshots (demo mode) ---
        if force_mock:
            total_upserted += _seed_historical_prices(db, marketplace_account_id)

        # --- Seed ProductMaster and link ListingMap (demo mode) ---
        if force_mock:
            total_upserted += _seed_product_master(db, account.seller_id, marketplace_account_id)

        # --- Sync Mock Reviews (demo mode only) ---
        if force_mock or settings.USE_MOCK_DATA:
            mock_reviews = generate_mock_reviews(marketplace_account_id)
            total_fetched += len(mock_reviews)
            for review in mock_reviews:
                _upsert(db, CustomerReview, review, [
                    "rating", "title", "body", "reviewer_name", "review_date", "verified_purchase",
                ])
                total_upserted += 1
            db.flush()
            logger.info("Synced %d mock reviews", len(mock_reviews))

        # --- Run analytics (forecast + pricing) ---
        try:
            from app.services.forecast_service import compute_forecasts
            from app.services.pricing_service import compute_recommendations
            from app.services.sentiment_service import compute_all_insights

            compute_forecasts(db, marketplace_account_id)
            compute_recommendations(db, marketplace_account_id)
            compute_all_insights(db, marketplace_account_id)
        except Exception as e:
            logger.warning("Analytics computation failed (non-fatal): %s", e)

        # Update account last_sync_at
        account.last_sync_at = datetime.utcnow()
        sync_run.status = SyncRunStatus.COMPLETED
        sync_run.records_fetched = total_fetched
        sync_run.records_upserted = total_upserted
        sync_run.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Sync completed: account={marketplace_account_id}, fetched={total_fetched}, upserted={total_upserted}")

    except Exception as e:
        logger.exception(f"Sync failed for account {marketplace_account_id}")
        sync_run.status = SyncRunStatus.FAILED
        sync_run.error_log = str(e)[:2000]
        sync_run.completed_at = datetime.utcnow()
        db.commit()

    return sync_run
