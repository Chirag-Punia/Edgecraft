"""Dashboard KPIs — real queries against synced marketplace data."""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.enums import ChangeType, OrderStatus
from app.models.marketplace_account import MarketplaceAccount
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.inventory_snapshot import InventorySnapshot
from app.models.price_snapshot import PriceSnapshot
from app.models.user import User
from app.schemas.dashboard import (
    DashboardKPIs, KPIData,
    SalesTrendResponse, SalesTrendPoint,
    OrderStatusResponse, OrderStatusItem,
    TopProductsResponse, TopProduct,
    InventoryHealthResponse, InventoryHealthSummary, InventoryItem,
    PricingOverviewResponse, PricingLostItem,
)

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


def _pct_change(current: Decimal | None, previous: Decimal | None) -> tuple[str, ChangeType]:
    current = current or Decimal(0)
    previous = previous or Decimal(0)
    if previous == 0:
        if current > 0:
            return "+100%", ChangeType.POSITIVE
        return "0%", ChangeType.NEUTRAL
    change = ((current - previous) / previous * 100)
    sign = "+" if change >= 0 else ""
    change_type = ChangeType.POSITIVE if change >= 0 else ChangeType.NEGATIVE
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
            KPIData(title="Today's GMV", value="₹0", change="Connect a marketplace first", change_type=ChangeType.NEUTRAL),
            KPIData(title="Net Sales (30D)", value="₹0", change="No data yet", change_type=ChangeType.NEUTRAL),
            KPIData(title="Orders Today", value="0", change="No data yet", change_type=ChangeType.NEUTRAL),
            KPIData(title="Units Today", value="0", change="No data yet", change_type=ChangeType.NEUTRAL),
            KPIData(title="Return Rate", value="0%", change="No data yet", change_type=ChangeType.NEUTRAL),
            KPIData(title="Stockout Risks", value="0", change="No data yet", change_type=ChangeType.NEUTRAL),
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
    orders_type = ChangeType.POSITIVE if orders_diff >= 0 else ChangeType.NEGATIVE

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
        base_filter, Order.order_date >= thirty_days_ago, Order.status == OrderStatus.CANCELLED,
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
        KPIData(title="Net Sales (30D)", value=_fmt_inr(sales_30d), change="Last 30 days", change_type=ChangeType.POSITIVE),
        KPIData(title="Orders Today", value=str(orders_today or 0), change=f"{orders_sign}{orders_diff} from yesterday", change_type=orders_type),
        KPIData(title="Units Today", value=str(units_today or 0), change=f"{units_sign}{units_diff} from yesterday", change_type=ChangeType.POSITIVE if units_diff >= 0 else ChangeType.NEGATIVE),
        KPIData(title="Return Rate", value=f"{return_rate}%", change="Last 30 days", change_type=ChangeType.NEGATIVE if return_rate > 5 else ChangeType.POSITIVE),
        KPIData(title="Stockout Risks", value=str(stockout_count), change="Critical" if stockout_count > 3 else "Healthy", change_type=ChangeType.NEGATIVE if stockout_count > 3 else ChangeType.POSITIVE),
    ])


# ── Sales Trend (last 30 days) ─────────────────────────────────

@router.get("/sales-trend", response_model=SalesTrendResponse)
def get_sales_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return SalesTrendResponse(data=[])

    thirty_days_ago = date.today() - timedelta(days=30)
    rows = (
        db.query(
            func.date(Order.order_date).label("day"),
            func.coalesce(func.sum(Order.total_amount), 0).label("gmv"),
        )
        .filter(Order.marketplace_account_id.in_(account_ids), Order.order_date >= thirty_days_ago)
        .group_by(func.date(Order.order_date))
        .order_by(func.date(Order.order_date))
        .all()
    )
    return SalesTrendResponse(
        data=[SalesTrendPoint(day=str(r.day), gmv=float(r.gmv)) for r in rows]
    )


# ── Order Status Distribution ──────────────────────────────────

@router.get("/order-status", response_model=OrderStatusResponse)
def get_order_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return OrderStatusResponse(data=[])

    rows = (
        db.query(Order.status, func.count(Order.id).label("count"))
        .filter(Order.marketplace_account_id.in_(account_ids))
        .group_by(Order.status)
        .all()
    )
    return OrderStatusResponse(
        data=[OrderStatusItem(status=r.status, count=r.count) for r in rows]
    )


# ── Top Products by Revenue ────────────────────────────────────

@router.get("/top-products", response_model=TopProductsResponse)
def get_top_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return TopProductsResponse(data=[])

    rows = (
        db.query(
            OrderItem.asin,
            OrderItem.title,
            func.sum(OrderItem.unit_price * OrderItem.quantity_ordered).label("revenue"),
            func.sum(OrderItem.quantity_ordered).label("units_sold"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.marketplace_account_id.in_(account_ids))
        .group_by(OrderItem.asin, OrderItem.title)
        .order_by(func.sum(OrderItem.unit_price * OrderItem.quantity_ordered).desc())
        .limit(10)
        .all()
    )
    return TopProductsResponse(
        data=[
            TopProduct(
                asin=r.asin or "",
                title=r.title or "Unknown",
                revenue=float(r.revenue or 0),
                units_sold=int(r.units_sold or 0),
            )
            for r in rows
        ]
    )


# ── Inventory Health ───────────────────────────────────────────

@router.get("/inventory-health", response_model=InventoryHealthResponse)
def get_inventory_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return InventoryHealthResponse(
            summary=InventoryHealthSummary(total_skus=0, low_stock=0, healthy=0, overstocked=0),
            flagged_items=[],
        )

    today = date.today()
    snapshots = (
        db.query(InventorySnapshot)
        .filter(
            InventorySnapshot.marketplace_account_id.in_(account_ids),
            InventorySnapshot.snapshot_date == today,
        )
        .all()
    )

    total = len(snapshots)
    low = sum(1 for s in snapshots if s.fulfillable_quantity <= 10)
    over = sum(1 for s in snapshots if s.fulfillable_quantity >= 150)
    healthy = total - low - over

    # Flagged = low stock items, sorted by fulfillable ASC
    flagged = sorted(
        [s for s in snapshots if s.fulfillable_quantity <= 10],
        key=lambda s: s.fulfillable_quantity,
    )

    return InventoryHealthResponse(
        summary=InventoryHealthSummary(total_skus=total, low_stock=low, healthy=healthy, overstocked=over),
        flagged_items=[
            InventoryItem(
                seller_sku=s.seller_sku,
                asin=s.asin,
                fulfillable=s.fulfillable_quantity,
                inbound=s.inbound_quantity,
                total=s.total_quantity,
            )
            for s in flagged
        ],
    )


# ── Pricing Overview ──────────────────────────────────────────

@router.get("/pricing-overview", response_model=PricingOverviewResponse)
def get_pricing_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return PricingOverviewResponse(total_products=0, winning_count=0, win_rate=0.0, losing_items=[])

    today = date.today()
    snapshots = (
        db.query(PriceSnapshot)
        .filter(
            PriceSnapshot.marketplace_account_id.in_(account_ids),
            PriceSnapshot.snapshot_date == today,
        )
        .all()
    )

    total = len(snapshots)
    winning = sum(1 for s in snapshots if s.is_buybox_winner)
    win_rate = round(winning / total * 100, 1) if total > 0 else 0.0

    losing = [
        PricingLostItem(
            asin=s.asin,
            your_price=float(s.your_price or 0),
            buybox_price=float(s.buybox_price or 0),
            gap=round(float((s.your_price or 0) - (s.buybox_price or 0)), 2),
        )
        for s in snapshots
        if not s.is_buybox_winner and s.your_price and s.buybox_price
    ]
    losing.sort(key=lambda x: x.gap, reverse=True)

    return PricingOverviewResponse(
        total_products=total,
        winning_count=winning,
        win_rate=win_rate,
        losing_items=losing,
    )
