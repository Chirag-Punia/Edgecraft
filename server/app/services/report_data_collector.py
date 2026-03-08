"""Collect cross-domain data for AI report generation.

Each collector gathers raw metrics from multiple tables into a structured dict
that the LLM can reason about. No LLM calls here — pure SQL.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.inventory_snapshot import InventorySnapshot
from app.models.price_snapshot import PriceSnapshot
from app.models.demand_forecast import DemandForecast
from app.models.review_insight import ReviewInsight
from app.models.listing_map import ListingMap
from app.enums import OrderStatus

logger = logging.getLogger(__name__)


def _latest_date(db: Session, account_ids: list[int], model, date_col) -> date:
    if not account_ids:
        return date.today()
    result = db.query(func.max(date_col)).filter(
        model.marketplace_account_id.in_(account_ids)
    ).scalar()
    return result or date.today()


def _names(db: Session, account_ids: list[int], asins: list[str]) -> dict[str, str]:
    if not asins or not account_ids:
        return {}
    rows = db.query(ListingMap.asin, ListingMap.listing_title).filter(
        ListingMap.marketplace_account_id.in_(account_ids),
        ListingMap.asin.in_(list(set(a for a in asins if a))),
    ).all()
    lookup = {r.asin: r.listing_title for r in rows if r.listing_title}
    return {a: lookup.get(a, a) for a in asins}


def _dec(v) -> float:
    if v is None:
        return 0.0
    return float(v)


def collect_health_scorecard(db: Session, account_ids: list[int]) -> dict:
    today = date.today()
    week_ago = today - timedelta(days=7)
    prev_week = week_ago - timedelta(days=7)
    base = Order.marketplace_account_id.in_(account_ids)

    rev_curr = _dec(db.query(func.sum(Order.total_amount)).filter(
        base, Order.order_date >= week_ago).scalar())
    rev_prev = _dec(db.query(func.sum(Order.total_amount)).filter(
        base, Order.order_date >= prev_week, Order.order_date < week_ago).scalar())

    orders_curr = db.query(func.count(Order.id)).filter(base, Order.order_date >= week_ago).scalar() or 0
    cancelled = db.query(func.count(Order.id)).filter(
        base, Order.order_date >= week_ago,
        Order.status.in_([OrderStatus.CANCELLED, OrderStatus.CANCELED])
    ).scalar() or 0

    inv_date = _latest_date(db, account_ids, InventorySnapshot, InventorySnapshot.snapshot_date)
    total_skus = db.query(func.count(InventorySnapshot.id)).filter(
        InventorySnapshot.marketplace_account_id.in_(account_ids),
        InventorySnapshot.snapshot_date == inv_date).scalar() or 0
    low_stock = db.query(func.count(InventorySnapshot.id)).filter(
        InventorySnapshot.marketplace_account_id.in_(account_ids),
        InventorySnapshot.snapshot_date == inv_date,
        InventorySnapshot.fulfillable_quantity <= 10).scalar() or 0

    price_date = _latest_date(db, account_ids, PriceSnapshot, PriceSnapshot.snapshot_date)
    total_priced = db.query(func.count(PriceSnapshot.id)).filter(
        PriceSnapshot.marketplace_account_id.in_(account_ids),
        PriceSnapshot.snapshot_date == price_date).scalar() or 0
    buybox_wins = db.query(func.count(PriceSnapshot.id)).filter(
        PriceSnapshot.marketplace_account_id.in_(account_ids),
        PriceSnapshot.snapshot_date == price_date,
        PriceSnapshot.is_buybox_winner == True).scalar() or 0

    insight_date = _latest_date(db, account_ids, ReviewInsight, ReviewInsight.insight_date)
    sentiments = db.query(ReviewInsight.avg_sentiment).filter(
        ReviewInsight.marketplace_account_id.in_(account_ids),
        ReviewInsight.insight_date == insight_date).all()
    avg_sent = sum(_dec(s[0]) for s in sentiments) / len(sentiments) if sentiments else 0

    fc_date = _latest_date(db, account_ids, DemandForecast, DemandForecast.forecast_date)
    stockout_risk_count = db.query(func.count(DemandForecast.id)).filter(
        DemandForecast.marketplace_account_id.in_(account_ids),
        DemandForecast.forecast_date == fc_date,
        DemandForecast.horizon_days == 7,
        DemandForecast.stockout_risk == True).scalar() or 0

    return {
        "revenue_7d": rev_curr, "revenue_prev_7d": rev_prev,
        "orders_7d": orders_curr, "cancelled_7d": cancelled,
        "cancel_rate": round(cancelled / orders_curr * 100, 1) if orders_curr > 0 else 0,
        "total_skus": total_skus, "low_stock_skus": low_stock,
        "total_priced": total_priced, "buybox_wins": buybox_wins,
        "buybox_rate": round(buybox_wins / total_priced * 100, 1) if total_priced > 0 else 0,
        "avg_sentiment": round(avg_sent, 2),
        "stockout_risk_count": stockout_risk_count,
    }


def collect_product_matrix(db: Session, account_ids: list[int]) -> dict:
    today = date.today()
    month_ago = today - timedelta(days=30)

    # Top 15 products by revenue
    products = (
        db.query(
            OrderItem.asin,
            func.sum(OrderItem.unit_price * OrderItem.quantity_ordered).label("revenue"),
            func.sum(OrderItem.quantity_ordered).label("units"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.marketplace_account_id.in_(account_ids), Order.order_date >= month_ago)
        .group_by(OrderItem.asin)
        .order_by(func.sum(OrderItem.unit_price * OrderItem.quantity_ordered).desc())
        .limit(15)
        .all()
    )
    asins = [p.asin for p in products]
    names = _names(db, account_ids, asins)

    inv_date = _latest_date(db, account_ids, InventorySnapshot, InventorySnapshot.snapshot_date)
    inv_map = {}
    for row in db.query(InventorySnapshot.asin, InventorySnapshot.fulfillable_quantity).filter(
        InventorySnapshot.marketplace_account_id.in_(account_ids),
        InventorySnapshot.snapshot_date == inv_date, InventorySnapshot.asin.in_(asins)).all():
        inv_map[row.asin] = row.fulfillable_quantity

    price_date = _latest_date(db, account_ids, PriceSnapshot, PriceSnapshot.snapshot_date)
    buybox_map = {}
    for row in db.query(PriceSnapshot.asin, PriceSnapshot.is_buybox_winner).filter(
        PriceSnapshot.marketplace_account_id.in_(account_ids),
        PriceSnapshot.snapshot_date == price_date, PriceSnapshot.asin.in_(asins)).all():
        buybox_map[row.asin] = bool(row.is_buybox_winner)

    insight_date = _latest_date(db, account_ids, ReviewInsight, ReviewInsight.insight_date)
    sent_map = {}
    for row in db.query(ReviewInsight.asin, ReviewInsight.avg_sentiment, ReviewInsight.negative_count).filter(
        ReviewInsight.marketplace_account_id.in_(account_ids),
        ReviewInsight.insight_date == insight_date, ReviewInsight.asin.in_(asins)).all():
        sent_map[row.asin] = {"sentiment": _dec(row.avg_sentiment), "negatives": row.negative_count}

    fc_date = _latest_date(db, account_ids, DemandForecast, DemandForecast.forecast_date)
    risk_map = {}
    for row in db.query(DemandForecast.asin, DemandForecast.stockout_risk, DemandForecast.days_of_stock).filter(
        DemandForecast.marketplace_account_id.in_(account_ids),
        DemandForecast.forecast_date == fc_date, DemandForecast.horizon_days == 7,
        DemandForecast.asin.in_(asins)).all():
        risk_map[row.asin] = {"stockout_risk": bool(row.stockout_risk), "days_of_stock": row.days_of_stock}

    items = []
    for p in products:
        items.append({
            "asin": p.asin, "name": names.get(p.asin, p.asin),
            "revenue_30d": _dec(p.revenue), "units_30d": int(p.units or 0),
            "stock": inv_map.get(p.asin, None),
            "buybox_winner": buybox_map.get(p.asin, None),
            "sentiment": sent_map.get(p.asin, {}).get("sentiment"),
            "negative_reviews": sent_map.get(p.asin, {}).get("negatives", 0),
            "stockout_risk": risk_map.get(p.asin, {}).get("stockout_risk", False),
            "days_of_stock": risk_map.get(p.asin, {}).get("days_of_stock"),
        })

    return {"products": items}


def collect_revenue_leakage(db: Session, account_ids: list[int]) -> dict:
    today = date.today()
    month_ago = today - timedelta(days=30)
    base = Order.marketplace_account_id.in_(account_ids)

    total_rev = _dec(db.query(func.sum(Order.total_amount)).filter(
        base, Order.order_date >= month_ago).scalar())
    cancel_rev = _dec(db.query(func.sum(Order.total_amount)).filter(
        base, Order.order_date >= month_ago,
        Order.status.in_([OrderStatus.CANCELLED, OrderStatus.CANCELED])).scalar())

    price_date = _latest_date(db, account_ids, PriceSnapshot, PriceSnapshot.snapshot_date)
    losing = db.query(PriceSnapshot.asin, PriceSnapshot.your_price, PriceSnapshot.buybox_price).filter(
        PriceSnapshot.marketplace_account_id.in_(account_ids),
        PriceSnapshot.snapshot_date == price_date,
        PriceSnapshot.is_buybox_winner == False,
        PriceSnapshot.your_price.isnot(None), PriceSnapshot.buybox_price.isnot(None)).all()

    asins_losing = [r.asin for r in losing]
    names = _names(db, account_ids, asins_losing)
    pricing_losses = [
        {"asin": r.asin, "name": names.get(r.asin, r.asin),
         "your_price": _dec(r.your_price), "buybox_price": _dec(r.buybox_price),
         "gap": round(_dec(r.your_price) - _dec(r.buybox_price), 2)}
        for r in losing
    ]

    fc_date = _latest_date(db, account_ids, DemandForecast, DemandForecast.forecast_date)
    stockouts = db.query(DemandForecast.asin, DemandForecast.predicted_units, DemandForecast.days_of_stock).filter(
        DemandForecast.marketplace_account_id.in_(account_ids),
        DemandForecast.forecast_date == fc_date,
        DemandForecast.horizon_days == 7,
        DemandForecast.stockout_risk == True).all()
    stockout_names = _names(db, account_ids, [s.asin for s in stockouts])
    stockout_items = [
        {"asin": s.asin, "name": stockout_names.get(s.asin, s.asin),
         "predicted_units": s.predicted_units, "days_of_stock": s.days_of_stock}
        for s in stockouts
    ]

    return {
        "total_revenue_30d": total_rev,
        "cancellation_revenue_30d": cancel_rev,
        "pricing_losses": pricing_losses,
        "stockout_risks": stockout_items,
    }


def collect_weekly_digest(db: Session, account_ids: list[int]) -> dict:
    today = date.today()
    week_ago = today - timedelta(days=7)
    prev_week = week_ago - timedelta(days=7)
    base = Order.marketplace_account_id.in_(account_ids)

    rev_curr = _dec(db.query(func.sum(Order.total_amount)).filter(
        base, Order.order_date >= week_ago).scalar())
    rev_prev = _dec(db.query(func.sum(Order.total_amount)).filter(
        base, Order.order_date >= prev_week, Order.order_date < week_ago).scalar())
    orders_curr = db.query(func.count(Order.id)).filter(base, Order.order_date >= week_ago).scalar() or 0
    orders_prev = db.query(func.count(Order.id)).filter(
        base, Order.order_date >= prev_week, Order.order_date < week_ago).scalar() or 0

    # Top 5 products this week
    top_prods = (
        db.query(OrderItem.asin, func.sum(OrderItem.unit_price * OrderItem.quantity_ordered).label("rev"))
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.marketplace_account_id.in_(account_ids), Order.order_date >= week_ago)
        .group_by(OrderItem.asin)
        .order_by(func.sum(OrderItem.unit_price * OrderItem.quantity_ordered).desc())
        .limit(5).all()
    )
    names = _names(db, account_ids, [p.asin for p in top_prods])

    health = collect_health_scorecard(db, account_ids)

    return {
        "revenue_this_week": rev_curr, "revenue_last_week": rev_prev,
        "revenue_change_pct": round((rev_curr - rev_prev) / rev_prev * 100, 1) if rev_prev > 0 else 0,
        "orders_this_week": orders_curr, "orders_last_week": orders_prev,
        "top_products": [{"name": names.get(p.asin, p.asin), "revenue": _dec(p.rev)} for p in top_prods],
        "cancel_rate": health["cancel_rate"],
        "buybox_rate": health["buybox_rate"],
        "low_stock_count": health["low_stock_skus"],
        "stockout_risk_count": health["stockout_risk_count"],
        "avg_sentiment": health["avg_sentiment"],
    }


def collect_pricing_strategy(db: Session, account_ids: list[int]) -> dict:
    price_date = _latest_date(db, account_ids, PriceSnapshot, PriceSnapshot.snapshot_date)
    snapshots = db.query(PriceSnapshot).filter(
        PriceSnapshot.marketplace_account_id.in_(account_ids),
        PriceSnapshot.snapshot_date == price_date).all()

    asins = [s.asin for s in snapshots]
    names = _names(db, account_ids, asins)

    insight_date = _latest_date(db, account_ids, ReviewInsight, ReviewInsight.insight_date)
    sent_map = {}
    for r in db.query(ReviewInsight.asin, ReviewInsight.avg_sentiment).filter(
        ReviewInsight.marketplace_account_id.in_(account_ids),
        ReviewInsight.insight_date == insight_date, ReviewInsight.asin.in_(asins)).all():
        sent_map[r.asin] = _dec(r.avg_sentiment)

    # Revenue per ASIN last 30d
    today = date.today()
    month_ago = today - timedelta(days=30)
    rev_map = {}
    for r in db.query(OrderItem.asin, func.sum(OrderItem.unit_price * OrderItem.quantity_ordered).label("rev")).join(
        Order, OrderItem.order_id == Order.id).filter(
        Order.marketplace_account_id.in_(account_ids), Order.order_date >= month_ago).group_by(
        OrderItem.asin).all():
        rev_map[r.asin] = _dec(r.rev)

    items = []
    for s in snapshots:
        items.append({
            "asin": s.asin, "name": names.get(s.asin, s.asin),
            "your_price": _dec(s.your_price),
            "buybox_price": _dec(s.buybox_price),
            "lowest_price": _dec(s.lowest_price),
            "is_winner": bool(s.is_buybox_winner),
            "sentiment": sent_map.get(s.asin),
            "revenue_30d": rev_map.get(s.asin, 0),
        })

    items.sort(key=lambda x: x["revenue_30d"], reverse=True)
    return {"products": items[:15]}


COLLECTORS = {
    "business_health": collect_health_scorecard,
    "product_matrix": collect_product_matrix,
    "revenue_leakage": collect_revenue_leakage,
    "weekly_digest": collect_weekly_digest,
    "pricing_strategy": collect_pricing_strategy,
}
