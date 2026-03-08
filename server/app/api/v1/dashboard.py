"""Dashboard KPIs — real queries against synced marketplace data."""
import logging
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
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
from app.models.demand_forecast import DemandForecast
from app.models.review_insight import ReviewInsight
from app.models.listing_map import ListingMap
from app.models.user import User
from app.schemas.dashboard import (
    DashboardKPIs, KPIData,
    SalesTrendResponse, SalesTrendPoint,
    OrderStatusResponse, OrderStatusItem,
    TopProductsResponse, TopProduct,
    InventoryHealthResponse, InventoryHealthSummary, InventoryItem,
    PricingOverviewResponse, PricingLostItem,
    ActionItemsResponse, ActionItem,
    DemandForecastResponse, DemandForecastItem,
    SentimentOverviewResponse, SentimentItem,
    CitySalesResponse, CitySalesItem,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ── Helpers ──────────────────────────────────────────────────────

def _get_account_ids(db: Session, seller_id: int | None) -> list[int]:
    if not seller_id:
        return []
    return [
        a.id for a in db.query(MarketplaceAccount.id)
        .filter(MarketplaceAccount.seller_id == seller_id)
        .all()
    ]


def _fmt_inr(amount: Decimal | None) -> str:
    if amount is None:
        return "₹0"
    amt = int(amount)
    if amt == 0:
        return "₹0"
    s = str(abs(amt))
    if len(s) <= 3:
        formatted = s
    else:
        formatted = s[-3:]
        s = s[:-3]
        while s:
            formatted = s[-2:] + "," + formatted
            s = s[:-2]
    return f"₹{'-' if amt < 0 else ''}{formatted}"


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


def _latest_snapshot(db: Session, account_ids: list[int], model, date_col) -> date:
    """Get latest available snapshot date using ORM."""
    if not account_ids:
        return date.today()
    try:
        result = db.query(func.max(date_col)).filter(
            model.marketplace_account_id.in_(account_ids)
        ).scalar()
        if result:
            return result
    except Exception as e:
        logger.warning("Snapshot date lookup failed for %s: %s", model.__tablename__, e)
    return date.today()


def _product_names(db: Session, account_ids: list[int], asins: list[str]) -> dict[str, str]:
    """Batch lookup product names. Returns {asin: name}."""
    if not asins or not account_ids:
        return {}
    unique = list(set(a for a in asins if a))
    rows = (
        db.query(ListingMap.asin, ListingMap.listing_title)
        .filter(ListingMap.marketplace_account_id.in_(account_ids), ListingMap.asin.in_(unique))
        .all()
    )
    lookup = {r.asin: r.listing_title for r in rows if r.listing_title}
    return {asin: lookup.get(asin, asin or "Unknown") for asin in asins}


ALLOWED_DAYS = (7, 30, 90)


def _period_end() -> date:
    """End of current period = tomorrow (to include today's datetime records)."""
    return date.today() + timedelta(days=1)


# ── KPIs ─────────────────────────────────────────────────────────

@router.get("/kpis", response_model=DashboardKPIs)
def get_kpis(
    days: int = Query(30, description="Time window: 7, 30, or 90"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    days = days if days in ALLOWED_DAYS else 30
    account_ids = _get_account_ids(db, current_user.seller_id)
    label = f"{days}D"

    if not account_ids:
        return DashboardKPIs(kpis=[
            KPIData(title=f"Revenue ({label})", value="₹0", change="Connect a marketplace", change_type=ChangeType.NEUTRAL),
            KPIData(title=f"Orders ({label})", value="0", change="No data yet", change_type=ChangeType.NEUTRAL),
            KPIData(title="Avg Order Value", value="₹0", change="No data yet", change_type=ChangeType.NEUTRAL),
            KPIData(title="Cancel Rate", value="0%", change="No data yet", change_type=ChangeType.NEUTRAL),
            KPIData(title="Buy Box Win %", value="--", change="No data yet", change_type=ChangeType.NEUTRAL),
            KPIData(title="Stockout Risks", value="0", change="No data yet", change_type=ChangeType.NEUTRAL),
        ])

    end = _period_end()
    period_start = date.today() - timedelta(days=days)
    prev_start = period_start - timedelta(days=days)
    base = Order.marketplace_account_id.in_(account_ids)

    # 1. Revenue with comparison
    revenue_current = db.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
        base, Order.order_date >= period_start, Order.order_date < end,
    ).scalar()
    revenue_prev = db.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
        base, Order.order_date >= prev_start, Order.order_date < period_start,
    ).scalar()
    rev_change, rev_type = _pct_change(revenue_current, revenue_prev)

    # 2. Orders with comparison
    orders_current = db.query(func.count(Order.id)).filter(
        base, Order.order_date >= period_start, Order.order_date < end,
    ).scalar() or 0
    orders_prev = db.query(func.count(Order.id)).filter(
        base, Order.order_date >= prev_start, Order.order_date < period_start,
    ).scalar() or 0
    orders_change, orders_type = _pct_change(Decimal(orders_current), Decimal(orders_prev))

    # 3. AOV
    aov = round(float(revenue_current) / orders_current, 0) if orders_current > 0 else 0

    # 4. Cancel Rate
    cancelled = db.query(func.count(Order.id)).filter(
        base, Order.order_date >= period_start, Order.order_date < end,
        Order.status.in_([OrderStatus.CANCELLED, OrderStatus.CANCELED]),
    ).scalar() or 0
    cancel_rate = round(cancelled / orders_current * 100, 1) if orders_current > 0 else 0.0

    # 5. Buy Box Win Rate
    snap_date = _latest_snapshot(db, account_ids, PriceSnapshot, PriceSnapshot.snapshot_date)
    total_priced = db.query(func.count(PriceSnapshot.id)).filter(
        PriceSnapshot.marketplace_account_id.in_(account_ids),
        PriceSnapshot.snapshot_date == snap_date,
    ).scalar() or 0
    winning = db.query(func.count(PriceSnapshot.id)).filter(
        PriceSnapshot.marketplace_account_id.in_(account_ids),
        PriceSnapshot.snapshot_date == snap_date,
        PriceSnapshot.is_buybox_winner == True,
    ).scalar() or 0
    buybox_rate = round(winning / total_priced * 100, 1) if total_priced > 0 else 0.0

    # 6. Stockout Risks
    forecast_date = _latest_snapshot(db, account_ids, DemandForecast, DemandForecast.forecast_date)
    stockout_count = db.query(func.count(DemandForecast.id)).filter(
        DemandForecast.marketplace_account_id.in_(account_ids),
        DemandForecast.forecast_date == forecast_date,
        DemandForecast.horizon_days == 7,
        DemandForecast.stockout_risk == True,
    ).scalar() or 0
    if stockout_count == 0:
        inv_date = _latest_snapshot(db, account_ids, InventorySnapshot, InventorySnapshot.snapshot_date)
        stockout_count = db.query(func.count(InventorySnapshot.id)).filter(
            InventorySnapshot.marketplace_account_id.in_(account_ids),
            InventorySnapshot.snapshot_date == inv_date,
            InventorySnapshot.fulfillable_quantity <= 5,
        ).scalar() or 0

    return DashboardKPIs(kpis=[
        KPIData(title=f"Revenue ({label})", value=_fmt_inr(revenue_current),
                change=f"{rev_change} vs prev {label}", change_type=rev_type),
        KPIData(title=f"Orders ({label})", value=str(orders_current),
                change=f"{orders_change} vs prev {label}", change_type=orders_type),
        KPIData(title="Avg Order Value", value=_fmt_inr(Decimal(aov)),
                change=f"Based on {orders_current} orders", change_type=ChangeType.NEUTRAL),
        KPIData(title="Cancel Rate", value=f"{cancel_rate}%",
                change=f"{cancelled} cancelled of {orders_current}",
                change_type=ChangeType.NEGATIVE if cancel_rate > 5 else ChangeType.POSITIVE),
        KPIData(title="Buy Box Win %",
                value=f"{buybox_rate}%" if total_priced > 0 else "--",
                change=f"{winning}/{total_priced} products" if total_priced > 0 else "No pricing data",
                change_type=ChangeType.NEGATIVE if buybox_rate < 60 else ChangeType.POSITIVE),
        KPIData(title="Stockout Risks", value=str(stockout_count),
                change="Needs attention" if stockout_count > 0 else "All healthy",
                change_type=ChangeType.NEGATIVE if stockout_count > 0 else ChangeType.POSITIVE),
    ])


# ── Sales Trend ──────────────────────────────────────────────────

@router.get("/sales-trend", response_model=SalesTrendResponse)
def get_sales_trend(
    days: int = Query(30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    days = days if days in ALLOWED_DAYS else 30
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return SalesTrendResponse(data=[])

    start = date.today() - timedelta(days=days)
    rows = (
        db.query(
            func.date(Order.order_date).label("day"),
            func.coalesce(func.sum(Order.total_amount), 0).label("gmv"),
            func.count(Order.id).label("order_count"),
        )
        .filter(Order.marketplace_account_id.in_(account_ids), Order.order_date >= start)
        .group_by(func.date(Order.order_date))
        .order_by(func.date(Order.order_date))
        .all()
    )
    return SalesTrendResponse(
        data=[SalesTrendPoint(day=str(r.day), gmv=float(r.gmv), order_count=int(r.order_count)) for r in rows]
    )


# ── Order Status ─────────────────────────────────────────────────

@router.get("/order-status", response_model=OrderStatusResponse)
def get_order_status(
    days: int = Query(30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    days = days if days in ALLOWED_DAYS else 30
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return OrderStatusResponse(data=[])

    start = date.today() - timedelta(days=days)
    rows = (
        db.query(Order.status, func.count(Order.id).label("count"))
        .filter(Order.marketplace_account_id.in_(account_ids), Order.order_date >= start)
        .group_by(Order.status)
        .all()
    )
    return OrderStatusResponse(
        data=[OrderStatusItem(status=r.status, count=r.count) for r in rows]
    )


# ── Top Products ─────────────────────────────────────────────────

@router.get("/top-products", response_model=TopProductsResponse)
def get_top_products(
    days: int = Query(30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    days = days if days in ALLOWED_DAYS else 30
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return TopProductsResponse(data=[])

    start = date.today() - timedelta(days=days)
    rows = (
        db.query(
            OrderItem.asin,
            OrderItem.title,
            func.sum(OrderItem.unit_price * OrderItem.quantity_ordered).label("revenue"),
            func.sum(OrderItem.quantity_ordered).label("units_sold"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.marketplace_account_id.in_(account_ids), Order.order_date >= start)
        .group_by(OrderItem.asin, OrderItem.title)
        .order_by(func.sum(OrderItem.unit_price * OrderItem.quantity_ordered).desc())
        .limit(10)
        .all()
    )
    return TopProductsResponse(
        data=[
            TopProduct(asin=r.asin or "", title=r.title or "Unknown",
                       revenue=float(r.revenue or 0), units_sold=int(r.units_sold or 0))
            for r in rows
        ]
    )


# ── Inventory Health ─────────────────────────────────────────────

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

    snap_date = _latest_snapshot(db, account_ids, InventorySnapshot, InventorySnapshot.snapshot_date)
    snapshots = (
        db.query(InventorySnapshot)
        .filter(InventorySnapshot.marketplace_account_id.in_(account_ids),
                InventorySnapshot.snapshot_date == snap_date)
        .all()
    )

    total = len(snapshots)
    low = sum(1 for s in snapshots if s.fulfillable_quantity <= 10)
    over = sum(1 for s in snapshots if s.fulfillable_quantity >= 150)
    healthy = total - low - over

    flagged = sorted(
        [s for s in snapshots if s.fulfillable_quantity <= 10],
        key=lambda s: s.fulfillable_quantity,
    )

    # Batch product name lookup
    names = _product_names(db, account_ids, [s.asin for s in flagged if s.asin])

    return InventoryHealthResponse(
        summary=InventoryHealthSummary(total_skus=total, low_stock=low, healthy=healthy, overstocked=over),
        flagged_items=[
            InventoryItem(
                seller_sku=s.seller_sku, asin=s.asin,
                product_name=names.get(s.asin) if s.asin else None,
                fulfillable=s.fulfillable_quantity,
                inbound=s.inbound_quantity, total=s.total_quantity,
            )
            for s in flagged
        ],
    )


# ── Pricing Overview ────────────────────────────────────────────

@router.get("/pricing-overview", response_model=PricingOverviewResponse)
def get_pricing_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return PricingOverviewResponse(total_products=0, winning_count=0, win_rate=0.0, losing_items=[])

    snap_date = _latest_snapshot(db, account_ids, PriceSnapshot, PriceSnapshot.snapshot_date)
    snapshots = (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.marketplace_account_id.in_(account_ids),
                PriceSnapshot.snapshot_date == snap_date)
        .all()
    )

    total = len(snapshots)
    winning_count = sum(1 for s in snapshots if s.is_buybox_winner)
    win_rate = round(winning_count / total * 100, 1) if total > 0 else 0.0

    losers = [s for s in snapshots if not s.is_buybox_winner and s.your_price and s.buybox_price]
    names = _product_names(db, account_ids, [s.asin for s in losers])

    losing = sorted(
        [
            PricingLostItem(
                asin=s.asin, product_name=names.get(s.asin),
                your_price=float(s.your_price or 0),
                buybox_price=float(s.buybox_price or 0),
                gap=round(float((s.your_price or 0) - (s.buybox_price or 0)), 2),
            )
            for s in losers
        ],
        key=lambda x: x.gap, reverse=True,
    )

    return PricingOverviewResponse(
        total_products=total, winning_count=winning_count,
        win_rate=win_rate, losing_items=losing,
    )


# ── Action Items ─────────────────────────────────────────────────

@router.get("/action-items", response_model=ActionItemsResponse)
def get_action_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account_ids = _get_account_ids(db, current_user.seller_id)
    items: list[ActionItem] = []
    if not account_ids:
        return ActionItemsResponse(items=items)

    # 1. Stockout risks from demand forecasts
    forecast_date = _latest_snapshot(db, account_ids, DemandForecast, DemandForecast.forecast_date)
    stockout_products = (
        db.query(DemandForecast.asin, DemandForecast.days_of_stock, DemandForecast.predicted_units)
        .filter(
            DemandForecast.marketplace_account_id.in_(account_ids),
            DemandForecast.forecast_date == forecast_date,
            DemandForecast.horizon_days == 7,
            DemandForecast.stockout_risk == True,
        )
        .order_by(DemandForecast.days_of_stock.asc())
        .limit(5)
        .all()
    )
    if stockout_products:
        names = _product_names(db, account_ids, [p.asin for p in stockout_products])
        for p in stockout_products:
            dos = p.days_of_stock or 0
            items.append(ActionItem(
                severity="critical" if dos <= 3 else "warning",
                category="inventory",
                title=f"Restock {names.get(p.asin, p.asin)}",
                detail=f"{dos} days of stock left — predicted demand: {p.predicted_units} units/week",
            ))

    # 2. Products losing buy box with large gap
    snap_date = _latest_snapshot(db, account_ids, PriceSnapshot, PriceSnapshot.snapshot_date)
    losing_buybox = (
        db.query(PriceSnapshot.asin, PriceSnapshot.your_price, PriceSnapshot.buybox_price)
        .filter(
            PriceSnapshot.marketplace_account_id.in_(account_ids),
            PriceSnapshot.snapshot_date == snap_date,
            PriceSnapshot.is_buybox_winner == False,
            PriceSnapshot.your_price.isnot(None),
            PriceSnapshot.buybox_price.isnot(None),
        )
        .all()
    )
    big_gap = sorted(
        [s for s in losing_buybox if s.your_price and s.buybox_price and float(s.your_price - s.buybox_price) > 20],
        key=lambda s: float(s.your_price - s.buybox_price),
        reverse=True,
    )[:3]
    if big_gap:
        names = _product_names(db, account_ids, [s.asin for s in big_gap])
        for s in big_gap:
            gap = float(s.your_price - s.buybox_price)
            items.append(ActionItem(
                severity="warning", category="pricing",
                title=f"Reprice {names.get(s.asin, s.asin)}",
                detail=f"₹{gap:.0f} above buy box — lower to ₹{float(s.buybox_price):.0f} to win",
            ))

    # 3. Negative sentiment alerts
    insight_date = _latest_snapshot(db, account_ids, ReviewInsight, ReviewInsight.insight_date)
    negative_products = (
        db.query(ReviewInsight.asin, ReviewInsight.negative_count,
                 ReviewInsight.positive_count, ReviewInsight.top_complaints)
        .filter(
            ReviewInsight.marketplace_account_id.in_(account_ids),
            ReviewInsight.insight_date == insight_date,
            ReviewInsight.negative_count > ReviewInsight.positive_count,
        )
        .order_by(ReviewInsight.negative_count.desc())
        .limit(3)
        .all()
    )
    if negative_products:
        names = _product_names(db, account_ids, [ri.asin for ri in negative_products])
        for ri in negative_products:
            complaints = ri.top_complaints[:2] if ri.top_complaints else []
            detail = f"{ri.negative_count} negative vs {ri.positive_count} positive reviews"
            if complaints:
                detail += f" — top issues: {', '.join(complaints)}"
            items.append(ActionItem(
                severity="warning", category="sentiment",
                title=f"Address reviews for {names.get(ri.asin, ri.asin)}",
                detail=detail,
            ))

    # 4. Pending/unshipped orders
    pending_count = db.query(func.count(Order.id)).filter(
        Order.marketplace_account_id.in_(account_ids),
        Order.status.in_([OrderStatus.PENDING, OrderStatus.UNSHIPPED]),
    ).scalar() or 0
    if pending_count > 0:
        items.append(ActionItem(
            severity="critical" if pending_count > 10 else "info",
            category="orders",
            title=f"{pending_count} orders awaiting shipment",
            detail="Ship ASAP to avoid late delivery penalties",
        ))

    return ActionItemsResponse(items=items)


# ── Demand Forecast ──────────────────────────────────────────────

@router.get("/demand-forecast", response_model=DemandForecastResponse)
def get_demand_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return DemandForecastResponse(data=[])

    forecast_date = _latest_snapshot(db, account_ids, DemandForecast, DemandForecast.forecast_date)
    rows = (
        db.query(DemandForecast)
        .filter(
            DemandForecast.marketplace_account_id.in_(account_ids),
            DemandForecast.forecast_date == forecast_date,
            DemandForecast.horizon_days == 7,
        )
        .order_by(DemandForecast.stockout_risk.desc(), DemandForecast.days_of_stock.asc())
        .limit(15)
        .all()
    )

    names = _product_names(db, account_ids, [r.asin for r in rows])

    return DemandForecastResponse(
        data=[
            DemandForecastItem(
                asin=r.asin, product_name=names.get(r.asin, r.asin),
                predicted_units=r.predicted_units,
                velocity_7d=float(r.velocity_7d or 0),
                days_of_stock=r.days_of_stock,
                stockout_risk=bool(r.stockout_risk),
            )
            for r in rows
        ]
    )


# ── Sentiment Overview ───────────────────────────────────────────

@router.get("/sentiment-overview", response_model=SentimentOverviewResponse)
def get_sentiment_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return SentimentOverviewResponse(avg_sentiment=None, total_reviews=0, data=[])

    insight_date = _latest_snapshot(db, account_ids, ReviewInsight, ReviewInsight.insight_date)
    rows = (
        db.query(ReviewInsight)
        .filter(
            ReviewInsight.marketplace_account_id.in_(account_ids),
            ReviewInsight.insight_date == insight_date,
        )
        .order_by(ReviewInsight.avg_sentiment.asc())
        .limit(20)
        .all()
    )

    if not rows:
        return SentimentOverviewResponse(avg_sentiment=None, total_reviews=0, data=[])

    total_reviews = sum(r.positive_count + r.negative_count + r.neutral_count for r in rows)
    avg_sent = sum(float(r.avg_sentiment or 0) for r in rows) / len(rows)

    names = _product_names(db, account_ids, [r.asin for r in rows])

    return SentimentOverviewResponse(
        avg_sentiment=round(avg_sent, 2),
        total_reviews=total_reviews,
        data=[
            SentimentItem(
                asin=r.asin, product_name=names.get(r.asin, r.asin),
                avg_sentiment=float(r.avg_sentiment or 0),
                positive=r.positive_count, negative=r.negative_count,
                neutral=r.neutral_count,
                top_complaints=r.top_complaints[:3] if r.top_complaints else [],
            )
            for r in rows
        ],
    )


# ── City-wise Sales ──────────────────────────────────────────────

@router.get("/city-sales", response_model=CitySalesResponse)
def get_city_sales(
    days: int = Query(30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    days = days if days in ALLOWED_DAYS else 30
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return CitySalesResponse(data=[])

    start = date.today() - timedelta(days=days)
    rows = (
        db.query(
            Order.ship_city,
            Order.ship_state,
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
        )
        .filter(
            Order.marketplace_account_id.in_(account_ids),
            Order.order_date >= start,
            Order.ship_city.isnot(None),
        )
        .group_by(Order.ship_city, Order.ship_state)
        .order_by(func.sum(Order.total_amount).desc())
        .limit(10)
        .all()
    )
    return CitySalesResponse(
        data=[
            CitySalesItem(city=r.ship_city, state=r.ship_state,
                          revenue=float(r.revenue), order_count=r.order_count)
            for r in rows
        ]
    )
