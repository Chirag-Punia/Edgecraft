"""Demand forecasting service using simple statistical methods.

Computes trailing sales velocity, moving averages, and linear trends
to predict demand and identify stockout risks.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.inventory_snapshot import InventorySnapshot
from app.models.demand_forecast import DemandForecast

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


def compute_forecasts(db: Session, marketplace_account_id: int):
    """Compute demand forecasts for all products of a marketplace account."""
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)

    # Get daily units sold per ASIN over last 30 days
    daily_sales = (
        db.query(
            OrderItem.asin,
            func.date(Order.order_date).label("day"),
            func.sum(OrderItem.quantity_ordered).label("units"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .filter(
            Order.marketplace_account_id == marketplace_account_id,
            Order.order_date >= thirty_days_ago,
        )
        .group_by(OrderItem.asin, func.date(Order.order_date))
        .all()
    )

    # Group by ASIN
    asin_daily: dict[str, dict[date, int]] = {}
    for row in daily_sales:
        if not row.asin:
            continue
        if row.asin not in asin_daily:
            asin_daily[row.asin] = {}
        asin_daily[row.asin][row.day] = int(row.units)

    # Get current inventory
    inventory = {
        r.asin: r.fulfillable_quantity
        for r in db.query(InventorySnapshot.asin, InventorySnapshot.fulfillable_quantity)
        .filter(
            InventorySnapshot.marketplace_account_id == marketplace_account_id,
            InventorySnapshot.snapshot_date == today,
        )
        .all()
        if r.asin
    }

    # Get SKU mapping
    sku_map = {
        r.asin: r.seller_sku
        for r in db.query(InventorySnapshot.asin, InventorySnapshot.seller_sku)
        .filter(
            InventorySnapshot.marketplace_account_id == marketplace_account_id,
            InventorySnapshot.snapshot_date == today,
        )
        .all()
        if r.asin
    }

    count = 0
    all_asins = set(asin_daily.keys()) | set(inventory.keys())

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

            values = {
                "marketplace_account_id": marketplace_account_id,
                "asin": asin,
                "seller_sku": sku_map.get(asin),
                "forecast_date": today,
                "horizon_days": horizon,
                "predicted_units": predicted,
                "confidence_lower": confidence_lower,
                "confidence_upper": confidence_upper,
                "velocity_7d": Decimal(str(round(velocity_7d, 2))),
                "velocity_30d": Decimal(str(round(velocity_30d, 2))),
                "days_of_stock": min(days_of_stock, 999),
                "stockout_risk": stockout_risk,
                "method": "linear_trend",
            }

            stmt = mysql_insert(DemandForecast).values(**values)
            stmt = stmt.on_duplicate_key_update(
                predicted_units=stmt.inserted.predicted_units,
                confidence_lower=stmt.inserted.confidence_lower,
                confidence_upper=stmt.inserted.confidence_upper,
                velocity_7d=stmt.inserted.velocity_7d,
                velocity_30d=stmt.inserted.velocity_30d,
                days_of_stock=stmt.inserted.days_of_stock,
                stockout_risk=stmt.inserted.stockout_risk,
                method=stmt.inserted.method,
            )
            db.execute(stmt)
            count += 1

    db.commit()
    logger.info("Computed %d forecasts (account=%d)", count, marketplace_account_id)
    return count
