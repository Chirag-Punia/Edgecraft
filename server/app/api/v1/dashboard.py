"""Dashboard KPIs — real queries against synced marketplace data (DynamoDB)."""
import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from boto3.dynamodb.conditions import Key, Attr

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.dynamo.helpers import query_all
from app.enums import AccountStatus, ChangeType, OrderStatus
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

def _get_account_ids(db, seller_id: int | None) -> list[int]:
    if not seller_id:
        return []
    table = db.get_table("marketplace_accounts")
    connected = AccountStatus.CONNECTED.value
    # Get ALL connected accounts (real + demo)
    items = query_all(
        table,
        IndexName="seller-index",
        KeyConditionExpression=Key("seller_id").eq(int(seller_id)),
        FilterExpression=Attr("status").eq(connected),
    )
    return [item["id"] for item in items]


def _fmt_inr(amount: float | Decimal | None) -> str:
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


def _pct_change(current: float | Decimal | None, previous: float | Decimal | None) -> tuple[str, ChangeType]:
    current = float(current or 0)
    previous = float(previous or 0)
    if previous == 0:
        if current > 0:
            return "+100%", ChangeType.POSITIVE
        return "0%", ChangeType.NEUTRAL
    change = ((current - previous) / previous * 100)
    sign = "+" if change >= 0 else ""
    change_type = ChangeType.POSITIVE if change >= 0 else ChangeType.NEGATIVE
    return f"{sign}{change:.1f}%", change_type


def _query_orders_by_date(db, account_ids: list[int], start: date, end: date) -> list[dict]:
    """Query orders across account_ids within a date range using account-date-index GSI."""
    table = db.get_table("orders")
    orders = []
    for aid in account_ids:
        items = query_all(
            table,
            IndexName="account-date-index",
            KeyConditionExpression=(
                Key("marketplace_account_id").eq(aid)
                & Key("order_date").between(start.isoformat(), end.isoformat())
            ),
        )
        orders.extend(items)
    return orders


def _latest_snapshot_date(db, account_ids: list[int], table_name: str, sk_field: str) -> date:
    """Get latest available snapshot date by scanning partitions and extracting dates from sort keys."""
    if not account_ids:
        return date.today()
    try:
        table = db.get_table(table_name)
        dates = set()
        for aid in account_ids:
            items = query_all(
                table,
                KeyConditionExpression=Key("marketplace_account_id").eq(aid),
                ProjectionExpression=sk_field,
            )
            for item in items:
                sk = item.get(sk_field, "")
                parts = sk.split("#")
                for part in parts:
                    try:
                        date.fromisoformat(part)
                        dates.add(part)
                        break
                    except (ValueError, TypeError):
                        continue
        if dates:
            return date.fromisoformat(max(dates))
    except Exception as e:
        logger.warning("Snapshot date lookup failed for %s: %s", table_name, e)
    return date.today()


def _get_snapshot_items(db, account_ids: list[int], table_name: str, sk_field: str, snap_date: date) -> list[dict]:
    """Get snapshot items for a given date by filtering sort keys that contain the date string."""
    table = db.get_table(table_name)
    date_str = snap_date.isoformat()
    items = []
    for aid in account_ids:
        all_items = query_all(
            table,
            KeyConditionExpression=Key("marketplace_account_id").eq(aid),
        )
        items.extend([i for i in all_items if date_str in i.get(sk_field, "")])
    return items


def _product_names(db, account_ids: list[int], asins: list[str]) -> dict[str, str]:
    """Batch lookup product names from listing_map. Returns {asin: name}."""
    if not asins or not account_ids:
        return {}
    unique = list(set(a for a in asins if a))
    if not unique:
        return {}
    table = db.get_table("listing_map")
    lookup = {}
    for aid in account_ids:
        items = query_all(
            table,
            KeyConditionExpression=Key("marketplace_account_id").eq(aid),
        )
        for item in items:
            if item.get("asin") in unique and item.get("listing_title"):
                lookup[item["asin"]] = item["listing_title"]
    return {asin: lookup.get(asin, asin or "Unknown") for asin in asins}


ALLOWED_DAYS = (7, 30, 90)


def _period_end() -> date:
    """End of current period = tomorrow (to include today's datetime records)."""
    return date.today() + timedelta(days=1)


# ── KPIs ─────────────────────────────────────────────────────────

@router.get("/kpis", response_model=DashboardKPIs)
def get_kpis(
    days: int = Query(30, description="Time window: 7, 30, or 90"),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
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

    # 1. Revenue with comparison
    orders_current_list = _query_orders_by_date(db, account_ids, period_start, end)
    orders_prev_list = _query_orders_by_date(db, account_ids, prev_start, period_start - timedelta(days=1))

    revenue_current = sum(float(o.get("total_amount", 0) or 0) for o in orders_current_list)
    revenue_prev = sum(float(o.get("total_amount", 0) or 0) for o in orders_prev_list)
    rev_change, rev_type = _pct_change(revenue_current, revenue_prev)

    # 2. Orders with comparison
    orders_current = len(orders_current_list)
    orders_prev = len(orders_prev_list)
    orders_change, orders_type = _pct_change(orders_current, orders_prev)

    # 3. AOV
    aov = round(revenue_current / orders_current, 0) if orders_current > 0 else 0

    # 4. Cancel Rate
    cancel_statuses = {OrderStatus.CANCELLED.value, OrderStatus.CANCELED.value}
    cancelled = sum(1 for o in orders_current_list if o.get("status") in cancel_statuses)
    cancel_rate = round(cancelled / orders_current * 100, 1) if orders_current > 0 else 0.0

    # 5. Buy Box Win Rate
    snap_date = _latest_snapshot_date(db, account_ids, "price_snapshots", "asin_date")
    price_items = _get_snapshot_items(db, account_ids, "price_snapshots", "asin_date", snap_date)
    total_priced = len(price_items)
    winning = sum(1 for p in price_items if p.get("is_buybox_winner"))
    buybox_rate = round(winning / total_priced * 100, 1) if total_priced > 0 else 0.0

    # 6. Stockout Risks
    fc_date = _latest_snapshot_date(db, account_ids, "demand_forecasts", "asin_date_horizon")
    fc_items = _get_snapshot_items(db, account_ids, "demand_forecasts", "asin_date_horizon", fc_date)
    stockout_count = sum(
        1 for f in fc_items
        if int(f.get("horizon_days", 0)) == 7 and f.get("stockout_risk")
    )
    if stockout_count == 0:
        inv_date = _latest_snapshot_date(db, account_ids, "inventory_snapshots", "sku_date")
        inv_items = _get_snapshot_items(db, account_ids, "inventory_snapshots", "sku_date", inv_date)
        stockout_count = sum(
            1 for i in inv_items
            if int(i.get("fulfillable_quantity", 0) or 0) <= 5
        )

    return DashboardKPIs(kpis=[
        KPIData(title=f"Revenue ({label})", value=_fmt_inr(revenue_current),
                change=f"{rev_change} vs prev {label}", change_type=rev_type),
        KPIData(title=f"Orders ({label})", value=str(orders_current),
                change=f"{orders_change} vs prev {label}", change_type=orders_type),
        KPIData(title="Avg Order Value", value=_fmt_inr(aov),
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
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    days = days if days in ALLOWED_DAYS else 30
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return SalesTrendResponse(data=[])

    start = date.today() - timedelta(days=days)
    end = _period_end()
    orders = _query_orders_by_date(db, account_ids, start, end)

    daily = defaultdict(lambda: {"gmv": 0.0, "order_count": 0})
    for o in orders:
        day = str(o.get("order_date", ""))[:10]
        daily[day]["gmv"] += float(o.get("total_amount", 0) or 0)
        daily[day]["order_count"] += 1

    data = sorted(
        [SalesTrendPoint(day=day, gmv=round(d["gmv"], 2), order_count=d["order_count"])
         for day, d in daily.items()],
        key=lambda x: x.day,
    )
    return SalesTrendResponse(data=data)


# ── Order Status ─────────────────────────────────────────────────

@router.get("/order-status", response_model=OrderStatusResponse)
def get_order_status(
    days: int = Query(30),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    days = days if days in ALLOWED_DAYS else 30
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return OrderStatusResponse(data=[])

    start = date.today() - timedelta(days=days)
    end = _period_end()
    orders = _query_orders_by_date(db, account_ids, start, end)

    status_counts = defaultdict(int)
    for o in orders:
        status_counts[o.get("status", "Unknown")] += 1

    return OrderStatusResponse(
        data=[OrderStatusItem(status=s, count=c) for s, c in status_counts.items()]
    )


# ── Top Products ─────────────────────────────────────────────────

@router.get("/top-products", response_model=TopProductsResponse)
def get_top_products(
    days: int = Query(30),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    days = days if days in ALLOWED_DAYS else 30
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return TopProductsResponse(data=[])

    start = date.today() - timedelta(days=days)
    end = _period_end()
    orders = _query_orders_by_date(db, account_ids, start, end)
    order_id_set = set(o["id"] for o in orders)

    # Query order items for these accounts, filter by order_ids in range
    oi_table = db.get_table("order_items")
    order_items = []
    for aid in account_ids:
        items = query_all(
            oi_table,
            IndexName="account-index",
            KeyConditionExpression=Key("marketplace_account_id").eq(aid),
        )
        order_items.extend([i for i in items if i.get("order_id") in order_id_set])

    # Aggregate by asin
    asin_data = defaultdict(lambda: {"title": None, "revenue": 0.0, "units_sold": 0})
    for it in order_items:
        asin = it.get("asin", "")
        asin_data[asin]["title"] = asin_data[asin]["title"] or it.get("title")
        price = float(it.get("unit_price", 0) or 0)
        qty = int(it.get("quantity_ordered", 0) or 0)
        asin_data[asin]["revenue"] += price * qty
        asin_data[asin]["units_sold"] += qty

    # Sort by revenue desc, take top 10
    sorted_products = sorted(asin_data.items(), key=lambda x: x[1]["revenue"], reverse=True)[:10]

    return TopProductsResponse(
        data=[
            TopProduct(
                asin=asin or "",
                title=data["title"] or "Unknown",
                revenue=round(data["revenue"], 2),
                units_sold=data["units_sold"],
            )
            for asin, data in sorted_products
        ]
    )


# ── Inventory Health ─────────────────────────────────────────────

@router.get("/inventory-health", response_model=InventoryHealthResponse)
def get_inventory_health(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return InventoryHealthResponse(
            summary=InventoryHealthSummary(total_skus=0, low_stock=0, healthy=0, overstocked=0),
            flagged_items=[],
        )

    snap_date = _latest_snapshot_date(db, account_ids, "inventory_snapshots", "sku_date")
    snapshots = _get_snapshot_items(db, account_ids, "inventory_snapshots", "sku_date", snap_date)

    total = len(snapshots)
    low = sum(1 for s in snapshots if int(s.get("fulfillable_quantity", 0) or 0) <= 10)
    over = sum(1 for s in snapshots if int(s.get("fulfillable_quantity", 0) or 0) >= 150)
    healthy = total - low - over

    flagged = sorted(
        [s for s in snapshots if int(s.get("fulfillable_quantity", 0) or 0) <= 10],
        key=lambda s: int(s.get("fulfillable_quantity", 0) or 0),
    )

    names = _product_names(db, account_ids, [s.get("asin") for s in flagged if s.get("asin")])

    return InventoryHealthResponse(
        summary=InventoryHealthSummary(total_skus=total, low_stock=low, healthy=healthy, overstocked=over),
        flagged_items=[
            InventoryItem(
                seller_sku=s.get("seller_sku", ""),
                asin=s.get("asin"),
                product_name=names.get(s.get("asin")) if s.get("asin") else None,
                fulfillable=int(s.get("fulfillable_quantity", 0) or 0),
                inbound=int(s.get("inbound_quantity", 0) or 0),
                total=int(s.get("total_quantity", 0) or 0),
            )
            for s in flagged
        ],
    )


# ── Pricing Overview ────────────────────────────────────────────

@router.get("/pricing-overview", response_model=PricingOverviewResponse)
def get_pricing_overview(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return PricingOverviewResponse(total_products=0, winning_count=0, win_rate=0.0, losing_items=[])

    snap_date = _latest_snapshot_date(db, account_ids, "price_snapshots", "asin_date")
    snapshots = _get_snapshot_items(db, account_ids, "price_snapshots", "asin_date", snap_date)

    total = len(snapshots)
    winning_count = sum(1 for s in snapshots if s.get("is_buybox_winner"))
    win_rate = round(winning_count / total * 100, 1) if total > 0 else 0.0

    losers = [
        s for s in snapshots
        if not s.get("is_buybox_winner") and s.get("your_price") and s.get("buybox_price")
    ]
    names = _product_names(db, account_ids, [s.get("asin") for s in losers])

    losing = sorted(
        [
            PricingLostItem(
                asin=s.get("asin", ""),
                product_name=names.get(s.get("asin")),
                your_price=float(s.get("your_price", 0) or 0),
                buybox_price=float(s.get("buybox_price", 0) or 0),
                gap=round(float(s.get("your_price", 0) or 0) - float(s.get("buybox_price", 0) or 0), 2),
            )
            for s in losers
        ],
        key=lambda x: x.gap,
        reverse=True,
    )

    return PricingOverviewResponse(
        total_products=total, winning_count=winning_count,
        win_rate=win_rate, losing_items=losing,
    )


# ── Action Items ─────────────────────────────────────────────────

@router.get("/action-items", response_model=ActionItemsResponse)
def get_action_items(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    account_ids = _get_account_ids(db, current_user.seller_id)
    items: list[ActionItem] = []
    if not account_ids:
        return ActionItemsResponse(items=items)

    # 1. Stockout risks from demand forecasts
    fc_date = _latest_snapshot_date(db, account_ids, "demand_forecasts", "asin_date_horizon")
    fc_items = _get_snapshot_items(db, account_ids, "demand_forecasts", "asin_date_horizon", fc_date)
    stockout_products = [
        f for f in fc_items
        if int(f.get("horizon_days", 0)) == 7 and f.get("stockout_risk")
    ]
    stockout_products.sort(key=lambda x: int(x.get("days_of_stock", 9999) or 9999))
    stockout_products = stockout_products[:5]

    if stockout_products:
        names = _product_names(db, account_ids, [p.get("asin") for p in stockout_products])
        for p in stockout_products:
            dos = int(p.get("days_of_stock", 0) or 0)
            asin = p.get("asin", "")
            items.append(ActionItem(
                severity="critical" if dos <= 3 else "warning",
                category="inventory",
                title=f"Restock {names.get(asin, asin)}",
                detail=f"{dos} days of stock left — predicted demand: {p.get('predicted_units', 0)} units/week",
            ))

    # 2. Products losing buy box with large gap
    snap_date = _latest_snapshot_date(db, account_ids, "price_snapshots", "asin_date")
    price_items = _get_snapshot_items(db, account_ids, "price_snapshots", "asin_date", snap_date)
    losing_buybox = [
        s for s in price_items
        if not s.get("is_buybox_winner")
        and s.get("your_price") is not None
        and s.get("buybox_price") is not None
    ]
    big_gap = sorted(
        [
            s for s in losing_buybox
            if s.get("your_price") and s.get("buybox_price")
            and float(s["your_price"]) - float(s["buybox_price"]) > 20
        ],
        key=lambda s: float(s["your_price"]) - float(s["buybox_price"]),
        reverse=True,
    )[:3]

    if big_gap:
        names = _product_names(db, account_ids, [s.get("asin") for s in big_gap])
        for s in big_gap:
            gap = float(s["your_price"]) - float(s["buybox_price"])
            asin = s.get("asin", "")
            items.append(ActionItem(
                severity="warning", category="pricing",
                title=f"Reprice {names.get(asin, asin)}",
                detail=f"₹{gap:.0f} above buy box — lower to ₹{float(s['buybox_price']):.0f} to win",
            ))

    # 3. Negative sentiment alerts
    insight_date = _latest_snapshot_date(db, account_ids, "review_insights", "asin_date")
    insight_items = _get_snapshot_items(db, account_ids, "review_insights", "asin_date", insight_date)
    negative_products = [
        ri for ri in insight_items
        if int(ri.get("negative_count", 0) or 0) > int(ri.get("positive_count", 0) or 0)
    ]
    negative_products.sort(key=lambda x: int(x.get("negative_count", 0) or 0), reverse=True)
    negative_products = negative_products[:3]

    if negative_products:
        names = _product_names(db, account_ids, [ri.get("asin") for ri in negative_products])
        for ri in negative_products:
            asin = ri.get("asin", "")
            complaints = (ri.get("top_complaints") or [])[:2]
            neg_count = int(ri.get("negative_count", 0) or 0)
            pos_count = int(ri.get("positive_count", 0) or 0)
            detail = f"{neg_count} negative vs {pos_count} positive reviews"
            if complaints:
                detail += f" — top issues: {', '.join(str(c) for c in complaints)}"
            items.append(ActionItem(
                severity="warning", category="sentiment",
                title=f"Address reviews for {names.get(asin, asin)}",
                detail=detail,
            ))

    # 4. Pending/unshipped orders
    orders_table = db.get_table("orders")
    pending_statuses = {OrderStatus.PENDING.value, OrderStatus.UNSHIPPED.value}
    all_pending = []
    for aid in account_ids:
        acct_orders = query_all(
            orders_table,
            IndexName="account-date-index",
            KeyConditionExpression=Key("marketplace_account_id").eq(aid),
            FilterExpression=Attr("status").is_in(list(pending_statuses)),
        )
        all_pending.extend(acct_orders)
    pending_count = len(all_pending)

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
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return DemandForecastResponse(data=[])

    fc_date = _latest_snapshot_date(db, account_ids, "demand_forecasts", "asin_date_horizon")
    fc_items = _get_snapshot_items(db, account_ids, "demand_forecasts", "asin_date_horizon", fc_date)

    # Filter to horizon_days=7
    rows = [f for f in fc_items if int(f.get("horizon_days", 0)) == 7]

    # Sort: stockout_risk desc, days_of_stock asc
    rows.sort(key=lambda x: (
        -(1 if x.get("stockout_risk") else 0),
        int(x.get("days_of_stock", 9999) or 9999),
    ))
    rows = rows[:15]

    names = _product_names(db, account_ids, [r.get("asin") for r in rows])

    return DemandForecastResponse(
        data=[
            DemandForecastItem(
                asin=r.get("asin", ""),
                product_name=names.get(r.get("asin", ""), r.get("asin", "")),
                predicted_units=int(r.get("predicted_units", 0) or 0),
                velocity_7d=float(r.get("velocity_7d", 0) or 0),
                days_of_stock=r.get("days_of_stock"),
                stockout_risk=bool(r.get("stockout_risk")),
            )
            for r in rows
        ]
    )


# ── Sentiment Overview ───────────────────────────────────────────

@router.get("/sentiment-overview", response_model=SentimentOverviewResponse)
def get_sentiment_overview(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return SentimentOverviewResponse(avg_sentiment=None, total_reviews=0, data=[])

    insight_date = _latest_snapshot_date(db, account_ids, "review_insights", "asin_date")
    rows = _get_snapshot_items(db, account_ids, "review_insights", "asin_date", insight_date)

    if not rows:
        return SentimentOverviewResponse(avg_sentiment=None, total_reviews=0, data=[])

    # Sort by avg_sentiment ASC, take top 20
    rows.sort(key=lambda x: float(x.get("avg_sentiment", 0) or 0))
    rows = rows[:20]

    total_reviews = sum(
        int(r.get("positive_count", 0) or 0)
        + int(r.get("negative_count", 0) or 0)
        + int(r.get("neutral_count", 0) or 0)
        for r in rows
    )
    avg_sent = sum(float(r.get("avg_sentiment", 0) or 0) for r in rows) / len(rows)

    names = _product_names(db, account_ids, [r.get("asin") for r in rows])

    return SentimentOverviewResponse(
        avg_sentiment=round(avg_sent, 2),
        total_reviews=total_reviews,
        data=[
            SentimentItem(
                asin=r.get("asin", ""),
                product_name=names.get(r.get("asin", ""), r.get("asin", "")),
                avg_sentiment=float(r.get("avg_sentiment", 0) or 0),
                positive=int(r.get("positive_count", 0) or 0),
                negative=int(r.get("negative_count", 0) or 0),
                neutral=int(r.get("neutral_count", 0) or 0),
                top_complaints=(r.get("top_complaints") or [])[:3],
            )
            for r in rows
        ],
    )


# ── City-wise Sales ──────────────────────────────────────────────

@router.get("/city-sales", response_model=CitySalesResponse)
def get_city_sales(
    days: int = Query(30),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    days = days if days in ALLOWED_DAYS else 30
    account_ids = _get_account_ids(db, current_user.seller_id)
    if not account_ids:
        return CitySalesResponse(data=[])

    start = date.today() - timedelta(days=days)
    end = _period_end()
    orders = _query_orders_by_date(db, account_ids, start, end)

    city_data = defaultdict(lambda: {"state": None, "order_count": 0, "revenue": 0.0})
    for o in orders:
        city = o.get("ship_city")
        if not city:
            continue
        city_data[city]["state"] = city_data[city]["state"] or o.get("ship_state")
        city_data[city]["order_count"] += 1
        city_data[city]["revenue"] += float(o.get("total_amount", 0) or 0)

    sorted_cities = sorted(city_data.items(), key=lambda x: x[1]["revenue"], reverse=True)[:10]

    return CitySalesResponse(
        data=[
            CitySalesItem(
                city=city,
                state=d["state"],
                revenue=round(d["revenue"], 2),
                order_count=d["order_count"],
            )
            for city, d in sorted_cities
        ]
    )
