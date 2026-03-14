"""ETL sync worker — fetches marketplace data, normalizes, and upserts into DynamoDB."""
import json
import logging
import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, date
from decimal import Decimal
from types import SimpleNamespace

from boto3.dynamodb.conditions import Key, Attr

from app.config import get_settings
from app.enums import Marketplace, SyncRunStatus, SyncType, ListingStatus
from app.dynamo.helpers import to_dynamo_item, from_dynamo_item, query_all, now_iso, batch_write_items
from app.services.mock_amazon_data import MockAmazonConnector, PRODUCTS
from app.services.amazon_connector import AmazonConnector
from app.services.mock_reviews_data import generate_mock_reviews

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_connector(account, force_mock: bool = False):
    """Pick mock or real connector based on config."""
    if force_mock or settings.USE_MOCK_DATA:
        logger.info("[Sync] Using MockAmazonConnector")
        return MockAmazonConnector()
    creds = json.loads(account.credentials_encrypted or "{}")
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


def _parse_amount(amount_obj) -> Decimal:
    """Extract amount from SP-API money object or raw value."""
    if isinstance(amount_obj, dict):
        return Decimal(str(amount_obj.get("Amount", "0")))
    return Decimal(str(amount_obj or "0"))


def _seed_historical_inventory(db, marketplace_account_id: int):
    """Generate 30 days of historical inventory snapshots for demo mode."""
    rng = random.Random(42)
    today = date.today()

    restock_products = {PRODUCTS[i]["sku"] for i in [2, 7, 11]}
    stockout_products = {PRODUCTS[i]["sku"] for i in [4, 9, 14]}

    table = db.get_table("inventory_snapshots")
    batch = []
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

            sku_date = f"{sku}#{snap_date.isoformat()}"
            item = {
                "marketplace_account_id": marketplace_account_id,
                "sku_date": sku_date,
                "seller_sku": sku,
                "asin": asin,
                "fnsku": fnsku,
                "fulfillable_quantity": fulfillable,
                "inbound_quantity": inbound,
                "reserved_quantity": reserved,
                "unfulfillable_quantity": unfulfillable,
                "total_quantity": total,
                "snapshot_date": snap_date.isoformat(),
            }
            batch.append(to_dynamo_item(item))

    batch_write_items(table, batch)
    logger.info("Seeded %d historical inventory snapshots", len(batch))
    return len(batch)


def _seed_historical_prices(db, marketplace_account_id: int):
    """Generate 30 days of historical price snapshots for demo mode."""
    rng = random.Random(42)
    today = date.today()

    buybox_losers = {PRODUCTS[i]["asin"] for i in [1, 5, 10, 15]}

    table = db.get_table("price_snapshots")
    batch = []
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

            asin_date = f"{asin}#{snap_date.isoformat()}"
            item = {
                "marketplace_account_id": marketplace_account_id,
                "asin_date": asin_date,
                "asin": asin,
                "seller_sku": sku,
                "your_price": Decimal(str(round(your_price, 2))),
                "landed_price": Decimal(str(round(your_price + rng.choice([0, 40, 60]), 2))),
                "buybox_price": Decimal(str(round(buybox_price, 2))),
                "lowest_price": Decimal(str(round(lowest_price, 2))),
                "is_buybox_winner": is_winner,
                "snapshot_date": snap_date.isoformat(),
            }
            batch.append(to_dynamo_item(item))

    batch_write_items(table, batch)
    logger.info("Seeded %d historical price snapshots", len(batch))
    return len(batch)


def _seed_product_master(db, seller_id: int, marketplace_account_id: int):
    """Seed ProductMaster records and link ListingMap entries for demo mode."""
    pm_table = db.get_table("product_master")
    lm_table = db.get_table("listing_map")

    count = 0
    for product in PRODUCTS:
        # Check existing product master by scanning for name match
        existing_items = query_all(
            pm_table,
            KeyConditionExpression=Key("seller_id").eq(seller_id),
            FilterExpression=Attr("name").eq(product["name"]),
        )

        if existing_items:
            pm = existing_items[0]
            # Update brand/category
            pm_table.update_item(
                Key={"seller_id": seller_id, "id": pm["id"]},
                UpdateExpression="SET brand = :b, category = :c",
                ExpressionAttributeValues={
                    ":b": product["brand"],
                    ":c": product["category"],
                },
            )
            pm_id = pm["id"]
        else:
            pm_id = db.next_id("product_master")
            now = now_iso()
            pm_item = {
                "seller_id": seller_id,
                "id": pm_id,
                "name": product["name"],
                "brand": product["brand"],
                "category": product["category"],
                "created_at": now,
                "updated_at": now,
            }
            pm_table.put_item(Item=to_dynamo_item(pm_item))
            count += 1

        # Link listing map entry
        listing_key = {
            "marketplace_account_id": marketplace_account_id,
            "marketplace_sku": product["sku"],
        }
        resp = lm_table.get_item(Key=listing_key)
        if "Item" in resp:
            lm_table.update_item(
                Key=listing_key,
                UpdateExpression="SET product_master_id = :pmid",
                ExpressionAttributeValues={":pmid": pm_id},
            )

    logger.info("Seeded %d ProductMaster records and linked ListingMap", count)
    return count


def _seed_product_master_batch(db, seller_id: int, marketplace_account_id: int):
    """Batch-seed ProductMaster records and link ListingMap entries for demo mode."""
    pm_table = db.get_table("product_master")
    lm_table = db.get_table("listing_map")

    start_id, _ = db.batch_next_id("product_master", len(PRODUCTS))
    now = now_iso()

    pm_items = []
    pm_id_map = {}
    for i, product in enumerate(PRODUCTS):
        pm_id = start_id + i
        pm_items.append(to_dynamo_item({
            "seller_id": seller_id,
            "id": pm_id,
            "name": product["name"],
            "brand": product["brand"],
            "category": product["category"],
            "created_at": now,
            "updated_at": now,
        }))
        pm_id_map[product["sku"]] = pm_id

    batch_write_items(pm_table, pm_items)

    # Link listing map entries (update_item can't be batched)
    for product in PRODUCTS:
        listing_key = {
            "marketplace_account_id": marketplace_account_id,
            "marketplace_sku": product["sku"],
        }
        resp = lm_table.get_item(Key=listing_key)
        if "Item" in resp:
            lm_table.update_item(
                Key=listing_key,
                UpdateExpression="SET product_master_id = :pmid",
                ExpressionAttributeValues={":pmid": pm_id_map[product["sku"]]},
            )

    logger.info("Batch-seeded %d ProductMaster records and linked ListingMap", len(PRODUCTS))
    return len(PRODUCTS)


def run_sync(db, marketplace_account_id: int, sync_type: SyncType = SyncType.FULL, force_mock: bool = False):
    """Run a full ETL sync for a marketplace account."""
    acct_table = db.get_table("marketplace_accounts")
    sync_table = db.get_table("sync_runs")
    orders_table = db.get_table("orders")
    order_items_table = db.get_table("order_items")
    inv_table = db.get_table("inventory_snapshots")
    price_table = db.get_table("price_snapshots")
    listing_table = db.get_table("listing_map")
    review_table = db.get_table("customer_reviews")

    # Get marketplace account
    resp = acct_table.get_item(Key={"id": marketplace_account_id})
    if "Item" not in resp:
        raise ValueError(f"MarketplaceAccount {marketplace_account_id} not found")
    account_data = from_dynamo_item(resp["Item"])
    account = SimpleNamespace(**account_data)

    # Create sync run
    sync_run_id = db.next_id("sync_runs")
    now = now_iso()
    sync_run_item = {
        "id": sync_run_id,
        "marketplace_account_id": marketplace_account_id,
        "sync_type": sync_type.value if hasattr(sync_type, "value") else sync_type,
        "status": SyncRunStatus.RUNNING.value,
        "started_at": now,
        "created_at": now,
        "updated_at": now,
    }
    sync_table.put_item(Item=to_dynamo_item(sync_run_item))

    total_fetched = 0
    total_upserted = 0

    try:
        connector = _get_connector(account, force_mock=force_mock)

        # --- Sync Orders ---
        last_sync = account_data.get("last_sync_at")
        if last_sync:
            try:
                created_after = datetime.fromisoformat(last_sync)
            except (ValueError, TypeError):
                created_after = datetime.utcnow() - timedelta(days=180)
        else:
            created_after = datetime.utcnow() - timedelta(days=180)

        raw_orders = connector.get_orders(created_after=created_after)
        _save_raw_dump(account.seller_id, "orders", sync_run_id, raw_orders)
        total_fetched += len(raw_orders)

        order_id_map = {}  # external_order_id -> db order id

        if force_mock:
            # --- FAST PATH: batch write orders (skip GSI lookups) ---
            order_start_id, _ = db.batch_next_id("orders", len(raw_orders))
            order_batch = []
            for i, raw_order in enumerate(raw_orders):
                ext_id = raw_order["AmazonOrderId"]
                order_date_str = raw_order.get("PurchaseDate", "")
                try:
                    order_date = datetime.fromisoformat(order_date_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    order_date = datetime.utcnow()

                total_amount = _parse_amount(raw_order.get("OrderTotal", {}))
                shipping_amount = _parse_amount(raw_order.get("ShippingPrice", 0))
                addr = raw_order.get("ShippingAddress", {})
                db_order_id = order_start_id + i
                acct_ext_order = f"{marketplace_account_id}#{ext_id}"

                order_batch.append(to_dynamo_item({
                    "id": db_order_id,
                    "marketplace_account_id": marketplace_account_id,
                    "external_order_id": ext_id,
                    "acct_ext_order": acct_ext_order,
                    "marketplace": Marketplace.AMAZON.value,
                    "status": raw_order.get("OrderStatus", "Unknown"),
                    "order_date": order_date.isoformat(),
                    "fulfillment_channel": raw_order.get("FulfillmentChannel"),
                    "currency": raw_order.get("OrderTotal", {}).get("CurrencyCode", "INR") if isinstance(raw_order.get("OrderTotal"), dict) else "INR",
                    "total_amount": total_amount,
                    "shipping_amount": shipping_amount,
                    "ship_city": addr.get("City"),
                    "ship_state": addr.get("StateOrRegion"),
                    "raw_payload": json.dumps(raw_order, default=str),
                    "created_at": now,
                    "updated_at": now,
                }))
                order_id_map[ext_id] = db_order_id

            batch_write_items(orders_table, order_batch)
            total_upserted += len(order_batch)

            # --- FAST PATH: batch write order items ---
            all_raw_items = []
            for raw_order in raw_orders:
                ext_id = raw_order["AmazonOrderId"]
                db_order_id = order_id_map.get(ext_id)
                if not db_order_id:
                    continue
                mock_items = raw_order.get("_mock_items")
                raw_items = connector.get_order_items(ext_id, _mock_items=mock_items)
                total_fetched += len(raw_items)
                for raw_item in raw_items:
                    all_raw_items.append((db_order_id, raw_item))

            if all_raw_items:
                oi_start_id, _ = db.batch_next_id("order_items", len(all_raw_items))
                oi_batch = []
                for i, (db_order_id, raw_item) in enumerate(all_raw_items):
                    oi_batch.append(to_dynamo_item({
                        "id": oi_start_id + i,
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
                        "created_at": now,
                        "updated_at": now,
                    }))
                batch_write_items(order_items_table, oi_batch)
                total_upserted += len(oi_batch)

        else:
            # --- STANDARD PATH: individual writes with GSI lookups ---
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

                # Look up existing order by acct_ext_order GSI
                acct_ext_order = f"{marketplace_account_id}#{ext_id}"
                existing_orders = query_all(
                    orders_table,
                    IndexName="acct-ext-order-index",
                    KeyConditionExpression=Key("acct_ext_order").eq(acct_ext_order),
                )

                if existing_orders:
                    db_order_id = existing_orders[0]["id"]
                else:
                    db_order_id = db.next_id("orders")

                order_item = {
                    "id": db_order_id,
                    "marketplace_account_id": marketplace_account_id,
                    "external_order_id": ext_id,
                    "acct_ext_order": acct_ext_order,
                    "marketplace": Marketplace.AMAZON.value,
                    "status": raw_order.get("OrderStatus", "Unknown"),
                    "order_date": order_date.isoformat(),
                    "fulfillment_channel": raw_order.get("FulfillmentChannel"),
                    "currency": raw_order.get("OrderTotal", {}).get("CurrencyCode", "INR") if isinstance(raw_order.get("OrderTotal"), dict) else "INR",
                    "total_amount": total_amount,
                    "shipping_amount": shipping_amount,
                    "ship_city": addr.get("City"),
                    "ship_state": addr.get("StateOrRegion"),
                    "raw_payload": json.dumps(raw_order, default=str),
                    "created_at": now,
                    "updated_at": now,
                }
                orders_table.put_item(Item=to_dynamo_item(order_item))
                order_id_map[ext_id] = db_order_id
                total_upserted += 1

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
                    ext_item_id = raw_item["OrderItemId"]

                    # Look up existing order item by order_id GSI + external_order_item_id filter
                    existing_items = query_all(
                        order_items_table,
                        IndexName="order-index",
                        KeyConditionExpression=Key("order_id").eq(db_order_id),
                        FilterExpression=Attr("external_order_item_id").eq(ext_item_id),
                    )

                    if existing_items:
                        item_db_id = existing_items[0]["id"]
                    else:
                        item_db_id = db.next_id("order_items")

                    oi_item = {
                        "id": item_db_id,
                        "order_id": db_order_id,
                        "marketplace_account_id": marketplace_account_id,
                        "external_order_item_id": ext_item_id,
                        "asin": raw_item.get("ASIN"),
                        "seller_sku": raw_item.get("SellerSKU"),
                        "title": raw_item.get("Title"),
                        "quantity_ordered": raw_item.get("QuantityOrdered", 1),
                        "quantity_shipped": raw_item.get("QuantityShipped", 0),
                        "unit_price": _parse_amount(raw_item.get("ItemPrice", {})),
                        "item_tax": _parse_amount(raw_item.get("ItemTax", {})),
                        "item_discount": _parse_amount(raw_item.get("PromotionDiscount", {})),
                        "created_at": now,
                        "updated_at": now,
                    }
                    order_items_table.put_item(Item=to_dynamo_item(oi_item))
                    total_upserted += 1

        # --- Sync Inventory ---
        raw_inventory = connector.get_inventory_summaries()
        _save_raw_dump(account.seller_id, "inventory", sync_run_id, raw_inventory)
        total_fetched += len(raw_inventory)
        today = date.today()

        known_asins = set()
        inv_batch = []
        listing_batch = []

        for item in raw_inventory:
            details = item.get("inventoryDetails", {})
            reserved = details.get("reservedQuantity", {})
            unfulfillable = details.get("unfulfillableQuantity", {})

            sku = item["sellerSku"]
            asin = item.get("asin")
            sku_date = f"{sku}#{today.isoformat()}"

            inv_item = {
                "marketplace_account_id": marketplace_account_id,
                "sku_date": sku_date,
                "seller_sku": sku,
                "asin": asin,
                "fnsku": item.get("fnSku"),
                "fulfillable_quantity": details.get("fulfillableQuantity", 0),
                "inbound_quantity": details.get("inboundWorkingQuantity", 0) + details.get("inboundShippedQuantity", 0),
                "reserved_quantity": reserved.get("totalReservedQuantity", 0) if isinstance(reserved, dict) else int(reserved or 0),
                "unfulfillable_quantity": unfulfillable.get("totalUnfulfillableQuantity", 0) if isinstance(unfulfillable, dict) else int(unfulfillable or 0),
                "total_quantity": item.get("totalQuantity", 0),
                "snapshot_date": today.isoformat(),
            }
            inv_batch.append(to_dynamo_item(inv_item))

            # Build listing map from inventory data
            known_asins.add(asin)
            listing_item = {
                "marketplace_account_id": marketplace_account_id,
                "marketplace_sku": sku,
                "asin": asin,
                "fnsku": item.get("fnSku"),
                "listing_title": item.get("productName"),
                "listing_status": ListingStatus.ACTIVE.value,
                "updated_at": now,
            }
            listing_batch.append(to_dynamo_item(listing_item))

        batch_write_items(inv_table, inv_batch)
        batch_write_items(listing_table, listing_batch)
        total_upserted += len(inv_batch) + len(listing_batch)

        # --- Seed historical inventory snapshots (demo mode) ---
        if force_mock:
            total_upserted += _seed_historical_inventory(db, marketplace_account_id)

        # --- Sync Pricing ---
        asin_list = [a for a in known_asins if a]
        if asin_list:
            raw_pricing = connector.get_competitive_pricing(asin_list)
            _save_raw_dump(account.seller_id, "pricing", sync_run_id, raw_pricing)
            total_fetched += len(raw_pricing)

            price_batch = []
            for item in raw_pricing:
                asin = item["ASIN"]
                asin_date = f"{asin}#{today.isoformat()}"

                price_item = {
                    "marketplace_account_id": marketplace_account_id,
                    "asin_date": asin_date,
                    "asin": asin,
                    "seller_sku": item.get("SellerSKU"),
                    "your_price": Decimal(str(item["YourPrice"])) if item.get("YourPrice") else None,
                    "landed_price": Decimal(str(item["LandedPrice"])) if item.get("LandedPrice") else None,
                    "buybox_price": Decimal(str(item["BuyBoxPrice"])) if item.get("BuyBoxPrice") else None,
                    "lowest_price": Decimal(str(item["LowestPrice"])) if item.get("LowestPrice") else None,
                    "is_buybox_winner": item.get("IsBuyBoxWinner", False),
                    "snapshot_date": today.isoformat(),
                }
                price_batch.append(to_dynamo_item(price_item))

            batch_write_items(price_table, price_batch)
            total_upserted += len(price_batch)

        # --- Seed historical price snapshots (demo mode) ---
        if force_mock:
            total_upserted += _seed_historical_prices(db, marketplace_account_id)

        # --- Seed ProductMaster and link ListingMap (demo mode) ---
        if force_mock:
            total_upserted += _seed_product_master_batch(db, account.seller_id, marketplace_account_id)

        # --- Sync Mock Reviews (demo mode only) ---
        if force_mock or settings.USE_MOCK_DATA:
            mock_reviews = generate_mock_reviews(marketplace_account_id)
            total_fetched += len(mock_reviews)
            review_batch = []
            for review in mock_reviews:
                review_item = {
                    "marketplace_account_id": review["marketplace_account_id"],
                    "external_review_id": review["external_review_id"],
                    "asin": review.get("asin"),
                    "seller_sku": review.get("seller_sku"),
                    "rating": review.get("rating"),
                    "title": review.get("title"),
                    "body": review.get("body"),
                    "reviewer_name": review.get("reviewer_name"),
                    "review_date": review["review_date"].isoformat() if isinstance(review.get("review_date"), (datetime, date)) else review.get("review_date"),
                    "verified_purchase": review.get("verified_purchase"),
                }
                review_batch.append(to_dynamo_item(review_item))
            batch_write_items(review_table, review_batch)
            total_upserted += len(review_batch)
            logger.info("Synced %d mock reviews", len(mock_reviews))

        # --- Run analytics (forecast + pricing + sentiment) ---
        try:
            from app.services.forecast_service import compute_forecasts
            from app.services.pricing_service import compute_recommendations
            from app.services.sentiment_service import compute_all_insights

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [
                    executor.submit(compute_forecasts, db, marketplace_account_id),
                    executor.submit(compute_recommendations, db, marketplace_account_id),
                    executor.submit(compute_all_insights, db, marketplace_account_id),
                ]
                for f in as_completed(futures):
                    f.result()
        except Exception as e:
            logger.warning("Analytics computation failed (non-fatal): %s", e)

        # Update account last_sync_at
        completed_at = now_iso()
        acct_table.update_item(
            Key={"id": marketplace_account_id},
            UpdateExpression="SET last_sync_at = :ls, updated_at = :ua",
            ExpressionAttributeValues={
                ":ls": completed_at,
                ":ua": completed_at,
            },
        )

        # Update sync run to completed
        sync_table.update_item(
            Key={"id": sync_run_id},
            UpdateExpression="SET #s = :s, records_fetched = :rf, records_upserted = :ru, completed_at = :ca, updated_at = :ua",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": SyncRunStatus.COMPLETED.value,
                ":rf": total_fetched,
                ":ru": total_upserted,
                ":ca": completed_at,
                ":ua": completed_at,
            },
        )

        logger.info(f"Sync completed: account={marketplace_account_id}, fetched={total_fetched}, upserted={total_upserted}")

    except Exception as e:
        logger.exception(f"Sync failed for account {marketplace_account_id}")
        failed_at = now_iso()
        sync_table.update_item(
            Key={"id": sync_run_id},
            UpdateExpression="SET #s = :s, error_log = :el, completed_at = :ca, updated_at = :ua",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": SyncRunStatus.FAILED.value,
                ":el": str(e)[:2000],
                ":ca": failed_at,
                ":ua": failed_at,
            },
        )

    # Return a sync_run-like object for callers
    resp = sync_table.get_item(Key={"id": sync_run_id})
    if "Item" in resp:
        return SimpleNamespace(**from_dynamo_item(resp["Item"]))
    return SimpleNamespace(**sync_run_item)
