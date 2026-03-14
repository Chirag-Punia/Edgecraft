"""Demand forecasting service using simple statistical methods.

Computes trailing sales velocity, moving averages, and linear trends
to predict demand and identify stockout risks.
"""
import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from boto3.dynamodb.conditions import Key

from app.dynamo.helpers import to_dynamo_item, query_all, now_iso, batch_write_items

logger = logging.getLogger(__name__)


def _compute_velocity(daily_units: list[float], window: int) -> float:
    """Compute average daily velocity over a window."""
    if not daily_units:
        return 0.0
    recent = daily_units[-window:] if len(daily_units) >= window else daily_units
    return sum(recent) / max(len(recent), 1)


def _linear_trend_predict(daily_units: list[float], horizon: int) -> int:
    """Simple linear trend prediction."""
    n = len(daily_units)
    if n < 3:
        avg = sum(daily_units) / max(n, 1)
        return max(0, int(avg * horizon))

    # Linear regression: y = a + b*x
    x_mean = (n - 1) / 2
    y_mean = sum(daily_units) / n
    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(daily_units))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return max(0, int(y_mean * horizon))

    b = numerator / denominator
    a = y_mean - b * x_mean

    # Predict total units for next `horizon` days
    total = sum(max(0, a + b * (n + d)) for d in range(horizon))
    return max(0, int(total))


def compute_forecasts(db, marketplace_account_id: int):
    """Compute demand forecasts for all products of a marketplace account."""
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)

    orders_table = db.get_table("orders")
    order_items_table = db.get_table("order_items")
    inv_table = db.get_table("inventory_snapshots")
    forecast_table = db.get_table("demand_forecasts")

    # Get all orders for this account in the last 30 days using account-date-index GSI
    orders = query_all(
        orders_table,
        IndexName="account-date-index",
        KeyConditionExpression=(
            Key("marketplace_account_id").eq(marketplace_account_id) &
            Key("order_date").gte(thirty_days_ago.isoformat())
        ),
    )

    # Build order_id -> order_date map
    order_date_map = {}
    order_ids = set()
    for o in orders:
        order_date_map[o["id"]] = o.get("order_date", "")
        order_ids.add(o["id"])

    # Get all order items for this account using account-index GSI
    all_items = query_all(
        order_items_table,
        IndexName="account-index",
        KeyConditionExpression=Key("marketplace_account_id").eq(marketplace_account_id),
    )

    # Filter items to only those belonging to orders in the last 30 days
    # Group by ASIN -> date -> total units
    asin_daily: dict[str, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for item in all_items:
        if item.get("order_id") not in order_ids:
            continue
        asin = item.get("asin")
        if not asin:
            continue
        order_date_str = order_date_map.get(item["order_id"], "")
        if not order_date_str:
            continue
        # Parse date (could be ISO datetime or date string)
        try:
            day = date.fromisoformat(order_date_str[:10])
        except (ValueError, TypeError):
            continue
        qty = int(item.get("quantity_ordered", 1))
        asin_daily[asin][day] += qty

    # Get current inventory — query all for this account, filter by today's snapshot_date
    today_iso = today.isoformat()
    inv_items = query_all(
        inv_table,
        KeyConditionExpression=Key("marketplace_account_id").eq(marketplace_account_id),
    )
    # Filter for today's date and build maps
    inventory = {}
    sku_map = {}
    for inv in inv_items:
        if inv.get("snapshot_date") != today_iso:
            continue
        asin = inv.get("asin")
        if asin:
            inventory[asin] = int(inv.get("fulfillable_quantity", 0))
            sku_map[asin] = inv.get("seller_sku")

    all_asins = set(asin_daily.keys()) | set(inventory.keys())
    forecast_batch = []

    for asin in all_asins:
        # Build daily series (fill missing days with 0)
        daily_dict = asin_daily.get(asin, {})
        daily_units = []
        for d in range(30):
            day = thirty_days_ago + timedelta(days=d)
            daily_units.append(float(daily_dict.get(day, 0)))

        velocity_7d = _compute_velocity(daily_units, 7)
        velocity_30d = _compute_velocity(daily_units, 30)
        current_stock = inventory.get(asin, 0)

        for horizon in (7, 14, 30):
            predicted = _linear_trend_predict(daily_units, horizon)
            confidence_lower = max(0, int(predicted * 0.7))
            confidence_upper = int(predicted * 1.3)

            days_of_stock = int(current_stock / velocity_7d) if velocity_7d > 0 else 999
            stockout_risk = days_of_stock < horizon

            forecast_date_str = today_iso
            asin_date_horizon = f"{asin}#{forecast_date_str}#{horizon}"
            now = now_iso()

            item = {
                "marketplace_account_id": marketplace_account_id,
                "asin_date_horizon": asin_date_horizon,
                "asin": asin,
                "seller_sku": sku_map.get(asin),
                "forecast_date": forecast_date_str,
                "horizon_days": horizon,
                "predicted_units": predicted,
                "confidence_lower": confidence_lower,
                "confidence_upper": confidence_upper,
                "velocity_7d": Decimal(str(round(velocity_7d, 2))),
                "velocity_30d": Decimal(str(round(velocity_30d, 2))),
                "days_of_stock": min(days_of_stock, 999),
                "stockout_risk": stockout_risk,
                "method": "linear_trend",
                "created_at": now,
                "updated_at": now,
            }

            forecast_batch.append(to_dynamo_item(item))

    if forecast_batch:
        batch_write_items(forecast_table, forecast_batch)

    logger.info("Computed %d forecasts (account=%d)", len(forecast_batch), marketplace_account_id)
    return len(forecast_batch)
