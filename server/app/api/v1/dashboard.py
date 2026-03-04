"""Dashboard KPIs — real queries against synced marketplace data."""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.marketplace_account import MarketplaceAccount
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.inventory_snapshot import InventorySnapshot
from app.models.user import User
from app.schemas.dashboard import DashboardKPIs, KPIData

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _get_account_ids(db: Session, seller_id: int | None) -> list[int]:
    if not seller_id:
        return []
    return [
        a.id for a in db.query(MarketplaceAccount.id)
        .filter(MarketplaceAccount.seller_id == seller_id)
        .all()
    ]


def _fmt_inr(amount: Decimal | None) -> str:
    if not amount:
        return "₹0"
    amt = int(amount)
    # Indian number formatting (e.g., 1,24,560)
    s = str(amt)
    if len(s) <= 3:
        return f"₹{s}"
    result = s[-3:]
    s = s[:-3]
    while s:
        result = s[-2:] + "," + result
        s = s[:-2]
    return f"₹{result}"


def _pct_change(current: Decimal | None, previous: Decimal | None) -> tuple[str, str]:
    current = current or Decimal(0)
    previous = previous or Decimal(0)
    if previous == 0:
        if current > 0:
            return "+100%", "positive"
        return "0%", "neutral"
    change = ((current - previous) / previous * 100)
    sign = "+" if change >= 0 else ""
    change_type = "positive" if change >= 0 else "negative"
    return f"{sign}{change:.1f}%", change_type


@router.get("/kpis", response_model=DashboardKPIs)
def get_kpis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compute real KPIs from synced marketplace data."""
    account_ids = _get_account_ids(db, current_user.seller_id)

    if not account_ids:
        return DashboardKPIs(kpis=[
            KPIData(title="Today's GMV", value="₹0", change="Connect a marketplace first", change_type="neutral"),
            KPIData(title="Net Sales (30D)", value="₹0", change="No data yet", change_type="neutral"),
            KPIData(title="Orders Today", value="0", change="No data yet", change_type="neutral"),
            KPIData(title="Units Today", value="0", change="No data yet", change_type="neutral"),
            KPIData(title="Return Rate", value="0%", change="No data yet", change_type="neutral"),
            KPIData(title="Stockout Risks", value="0", change="No data yet", change_type="neutral"),
        ])

    today = date.today()
    yesterday = today - timedelta(days=1)
    thirty_days_ago = today - timedelta(days=30)

    base_filter = Order.marketplace_account_id.in_(account_ids)

    # Today's GMV
    today_gmv = db.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
        base_filter, func.date(Order.order_date) == today
    ).scalar()
    yesterday_gmv = db.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
        base_filter, func.date(Order.order_date) == yesterday
    ).scalar()
    gmv_change, gmv_type = _pct_change(today_gmv, yesterday_gmv)

    # Net Sales (30D)
    sales_30d = db.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
        base_filter, Order.order_date >= thirty_days_ago
    ).scalar()

    # Orders today
    orders_today = db.query(func.count(Order.id)).filter(
        base_filter, func.date(Order.order_date) == today
    ).scalar()
    orders_yesterday = db.query(func.count(Order.id)).filter(
        base_filter, func.date(Order.order_date) == yesterday
    ).scalar()
    orders_diff = (orders_today or 0) - (orders_yesterday or 0)
    orders_sign = "+" if orders_diff >= 0 else ""
    orders_type = "positive" if orders_diff >= 0 else "negative"

    # Units today
    units_today = db.query(func.coalesce(func.sum(OrderItem.quantity_ordered), 0)).filter(
        OrderItem.marketplace_account_id.in_(account_ids),
        OrderItem.order_id.in_(
            db.query(Order.id).filter(base_filter, func.date(Order.order_date) == today)
        ),
    ).scalar()
    units_yesterday = db.query(func.coalesce(func.sum(OrderItem.quantity_ordered), 0)).filter(
        OrderItem.marketplace_account_id.in_(account_ids),
        OrderItem.order_id.in_(
            db.query(Order.id).filter(base_filter, func.date(Order.order_date) == yesterday)
        ),
    ).scalar()
    units_diff = (units_today or 0) - (units_yesterday or 0)
    units_sign = "+" if units_diff >= 0 else ""

    # Return rate (cancelled / total in last 30d)
    total_orders_30d = db.query(func.count(Order.id)).filter(
        base_filter, Order.order_date >= thirty_days_ago
    ).scalar() or 1
    cancelled_30d = db.query(func.count(Order.id)).filter(
        base_filter, Order.order_date >= thirty_days_ago, Order.status == "Cancelled"
    ).scalar() or 0
    return_rate = round(cancelled_30d / total_orders_30d * 100, 1)

    # Stockout risks (inventory items with fulfillable_quantity <= 5)
    stockout_count = db.query(func.count(InventorySnapshot.id)).filter(
        InventorySnapshot.marketplace_account_id.in_(account_ids),
        InventorySnapshot.snapshot_date == today,
        InventorySnapshot.fulfillable_quantity <= 5,
    ).scalar() or 0

    return DashboardKPIs(kpis=[
        KPIData(title="Today's GMV", value=_fmt_inr(today_gmv), change=f"{gmv_change} from yesterday", change_type=gmv_type),
        KPIData(title="Net Sales (30D)", value=_fmt_inr(sales_30d), change="Last 30 days", change_type="positive"),
        KPIData(title="Orders Today", value=str(orders_today or 0), change=f"{orders_sign}{orders_diff} from yesterday", change_type=orders_type),
        KPIData(title="Units Today", value=str(units_today or 0), change=f"{units_sign}{units_diff} from yesterday", change_type="positive" if units_diff >= 0 else "negative"),
        KPIData(title="Return Rate", value=f"{return_rate}%", change="Last 30 days", change_type="negative" if return_rate > 5 else "positive"),
        KPIData(title="Stockout Risks", value=str(stockout_count), change="Critical" if stockout_count > 3 else "Healthy", change_type="negative" if stockout_count > 3 else "positive"),
    ])
