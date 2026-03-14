"""Collect cross-domain data for AI report generation (DynamoDB version).

Each collector gathers raw metrics from multiple tables into a structured dict
that the LLM can reason about. No LLM calls here — pure DynamoDB queries + Python aggregation.
"""
import logging
from collections import defaultdict
from datetime import date, timedelta

from boto3.dynamodb.conditions import Key

from app.dynamo.helpers import query_all, query_by_account_ids
from app.enums import OrderStatus

logger = logging.getLogger(__name__)


def _dec(v) -> float:
    if v is None:
        return 0.0
    return float(v)


def _query_orders_in_range(db, account_ids: list[int], start: date, end: date) -> list[dict]:
    """Query orders within a date range across account_ids."""
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


def _query_order_items_for_orders(db, account_ids: list[int], order_ids: set) -> list[dict]:
    """Query order items for given account_ids, filter by order_ids."""
    if not order_ids:
        return []
    table = db.get_table("order_items")
    items = []
    for aid in account_ids:
        all_items = query_all(
            table,
            IndexName="account-index",
            KeyConditionExpression=Key("marketplace_account_id").eq(aid),
        )
        items.extend([i for i in all_items if i.get("order_id") in order_ids])
    return items


def _latest_date(db, account_ids: list[int], table_name: str, sk_field: str) -> date:
    """Get latest available date by scanning partitions and extracting dates from sort keys."""
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
        logger.warning("Latest date lookup failed for %s: %s", table_name, e)
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


def _names(db, account_ids: list[int], asins: list[str]) -> dict[str, str]:
    """Batch lookup product names from listing_map."""
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
    return {a: lookup.get(a, a) for a in asins}


def collect_health_scorecard(db, account_ids: list[int]) -> dict:
    today = date.today()
    week_ago = today - timedelta(days=7)
    prev_week = week_ago - timedelta(days=7)

    # Revenue and orders
    orders_curr = _query_orders_in_range(db, account_ids, week_ago, today)
    orders_prev = _query_orders_in_range(db, account_ids, prev_week, week_ago - timedelta(days=1))

    rev_curr = sum(_dec(o.get("total_amount")) for o in orders_curr)
    rev_prev = sum(_dec(o.get("total_amount")) for o in orders_prev)
    orders_curr_count = len(orders_curr)

    cancel_statuses = {OrderStatus.CANCELLED.value, OrderStatus.CANCELED.value}
    cancelled = sum(1 for o in orders_curr if o.get("status") in cancel_statuses)

    # Inventory
    inv_date = _latest_date(db, account_ids, "inventory_snapshots", "sku_date")
    inv_items = _get_snapshot_items(db, account_ids, "inventory_snapshots", "sku_date", inv_date)
    total_skus = len(inv_items)
    low_stock = sum(1 for i in inv_items if int(i.get("fulfillable_quantity", 0) or 0) <= 10)

    # Pricing
    price_date = _latest_date(db, account_ids, "price_snapshots", "asin_date")
    price_items = _get_snapshot_items(db, account_ids, "price_snapshots", "asin_date", price_date)
    total_priced = len(price_items)
    buybox_wins = sum(1 for p in price_items if p.get("is_buybox_winner"))

    # Sentiment
    insight_date = _latest_date(db, account_ids, "review_insights", "asin_date")
    insight_items = _get_snapshot_items(db, account_ids, "review_insights", "asin_date", insight_date)
    avg_sent = (
        sum(_dec(s.get("avg_sentiment")) for s in insight_items) / len(insight_items)
        if insight_items else 0
    )

    # Stockout risk
    fc_date = _latest_date(db, account_ids, "demand_forecasts", "asin_date_horizon")
    fc_items = _get_snapshot_items(db, account_ids, "demand_forecasts", "asin_date_horizon", fc_date)
    stockout_risk_count = sum(
        1 for f in fc_items
        if int(f.get("horizon_days", 0)) == 7 and f.get("stockout_risk")
    )

    return {
        "revenue_7d": rev_curr, "revenue_prev_7d": rev_prev,
        "orders_7d": orders_curr_count, "cancelled_7d": cancelled,
        "cancel_rate": round(cancelled / orders_curr_count * 100, 1) if orders_curr_count > 0 else 0,
        "total_skus": total_skus, "low_stock_skus": low_stock,
        "total_priced": total_priced, "buybox_wins": buybox_wins,
        "buybox_rate": round(buybox_wins / total_priced * 100, 1) if total_priced > 0 else 0,
        "avg_sentiment": round(avg_sent, 2),
        "stockout_risk_count": stockout_risk_count,
    }


def collect_product_matrix(db, account_ids: list[int]) -> dict:
    today = date.today()
    month_ago = today - timedelta(days=30)

    # Top 15 products by revenue
    orders = _query_orders_in_range(db, account_ids, month_ago, today)
    order_ids = set(o["id"] for o in orders)
    order_items = _query_order_items_for_orders(db, account_ids, order_ids)

    asin_agg = defaultdict(lambda: {"revenue": 0.0, "units": 0})
    for it in order_items:
        asin = it.get("asin", "")
        price = _dec(it.get("unit_price"))
        qty = int(it.get("quantity_ordered", 0) or 0)
        asin_agg[asin]["revenue"] += price * qty
        asin_agg[asin]["units"] += qty

    sorted_asins = sorted(asin_agg.items(), key=lambda x: x[1]["revenue"], reverse=True)[:15]
    asins = [a for a, _ in sorted_asins]
    names_map = _names(db, account_ids, asins)

    # Inventory snapshot
    inv_date = _latest_date(db, account_ids, "inventory_snapshots", "sku_date")
    inv_items = _get_snapshot_items(db, account_ids, "inventory_snapshots", "sku_date", inv_date)
    inv_map = {i.get("asin"): int(i.get("fulfillable_quantity", 0) or 0) for i in inv_items if i.get("asin")}

    # Price snapshot
    price_date = _latest_date(db, account_ids, "price_snapshots", "asin_date")
    price_items = _get_snapshot_items(db, account_ids, "price_snapshots", "asin_date", price_date)
    buybox_map = {p.get("asin"): bool(p.get("is_buybox_winner")) for p in price_items if p.get("asin")}

    # Sentiment
    insight_date = _latest_date(db, account_ids, "review_insights", "asin_date")
    insight_items = _get_snapshot_items(db, account_ids, "review_insights", "asin_date", insight_date)
    sent_map = {}
    for r in insight_items:
        if r.get("asin"):
            sent_map[r["asin"]] = {
                "sentiment": _dec(r.get("avg_sentiment")),
                "negatives": int(r.get("negative_count", 0) or 0),
            }

    # Demand forecast
    fc_date = _latest_date(db, account_ids, "demand_forecasts", "asin_date_horizon")
    fc_items = _get_snapshot_items(db, account_ids, "demand_forecasts", "asin_date_horizon", fc_date)
    risk_map = {}
    for f in fc_items:
        if int(f.get("horizon_days", 0)) == 7 and f.get("asin"):
            risk_map[f["asin"]] = {
                "stockout_risk": bool(f.get("stockout_risk")),
                "days_of_stock": f.get("days_of_stock"),
            }

    items = []
    for asin, data in sorted_asins:
        items.append({
            "asin": asin, "name": names_map.get(asin, asin),
            "revenue_30d": round(data["revenue"], 2), "units_30d": data["units"],
            "stock": inv_map.get(asin),
            "buybox_winner": buybox_map.get(asin),
            "sentiment": sent_map.get(asin, {}).get("sentiment"),
            "negative_reviews": sent_map.get(asin, {}).get("negatives", 0),
            "stockout_risk": risk_map.get(asin, {}).get("stockout_risk", False),
            "days_of_stock": risk_map.get(asin, {}).get("days_of_stock"),
        })

    return {"products": items}


def collect_revenue_leakage(db, account_ids: list[int]) -> dict:
    today = date.today()
    month_ago = today - timedelta(days=30)

    orders = _query_orders_in_range(db, account_ids, month_ago, today)
    total_rev = sum(_dec(o.get("total_amount")) for o in orders)

    cancel_statuses = {OrderStatus.CANCELLED.value, OrderStatus.CANCELED.value}
    cancel_rev = sum(
        _dec(o.get("total_amount"))
        for o in orders if o.get("status") in cancel_statuses
    )

    # Pricing losses
    price_date = _latest_date(db, account_ids, "price_snapshots", "asin_date")
    price_items = _get_snapshot_items(db, account_ids, "price_snapshots", "asin_date", price_date)
    losing = [
        p for p in price_items
        if not p.get("is_buybox_winner")
        and p.get("your_price") is not None
        and p.get("buybox_price") is not None
    ]

    asins_losing = [r.get("asin", "") for r in losing]
    names_map = _names(db, account_ids, asins_losing)
    pricing_losses = [
        {
            "asin": r.get("asin", ""), "name": names_map.get(r.get("asin", ""), r.get("asin", "")),
            "your_price": _dec(r.get("your_price")), "buybox_price": _dec(r.get("buybox_price")),
            "gap": round(_dec(r.get("your_price")) - _dec(r.get("buybox_price")), 2),
        }
        for r in losing
    ]

    # Stockout risks
    fc_date = _latest_date(db, account_ids, "demand_forecasts", "asin_date_horizon")
    fc_items = _get_snapshot_items(db, account_ids, "demand_forecasts", "asin_date_horizon", fc_date)
    stockouts = [
        f for f in fc_items
        if int(f.get("horizon_days", 0)) == 7 and f.get("stockout_risk")
    ]
    stockout_names = _names(db, account_ids, [s.get("asin", "") for s in stockouts])
    stockout_items = [
        {
            "asin": s.get("asin", ""), "name": stockout_names.get(s.get("asin", ""), s.get("asin", "")),
            "predicted_units": s.get("predicted_units"), "days_of_stock": s.get("days_of_stock"),
        }
        for s in stockouts
    ]

    return {
        "total_revenue_30d": total_rev,
        "cancellation_revenue_30d": cancel_rev,
        "pricing_losses": pricing_losses,
        "stockout_risks": stockout_items,
    }


def collect_weekly_digest(db, account_ids: list[int]) -> dict:
    today = date.today()
    week_ago = today - timedelta(days=7)
    prev_week = week_ago - timedelta(days=7)

    orders_curr = _query_orders_in_range(db, account_ids, week_ago, today)
    orders_prev = _query_orders_in_range(db, account_ids, prev_week, week_ago - timedelta(days=1))

    rev_curr = sum(_dec(o.get("total_amount")) for o in orders_curr)
    rev_prev = sum(_dec(o.get("total_amount")) for o in orders_prev)
    orders_curr_count = len(orders_curr)
    orders_prev_count = len(orders_prev)

    # Top 5 products this week
    order_ids = set(o["id"] for o in orders_curr)
    order_items = _query_order_items_for_orders(db, account_ids, order_ids)

    asin_rev = defaultdict(float)
    for it in order_items:
        asin = it.get("asin", "")
        price = _dec(it.get("unit_price"))
        qty = int(it.get("quantity_ordered", 0) or 0)
        asin_rev[asin] += price * qty

    top_asins = sorted(asin_rev.items(), key=lambda x: x[1], reverse=True)[:5]
    names_map = _names(db, account_ids, [a for a, _ in top_asins])

    health = collect_health_scorecard(db, account_ids)

    return {
        "revenue_this_week": rev_curr, "revenue_last_week": rev_prev,
        "revenue_change_pct": round((rev_curr - rev_prev) / rev_prev * 100, 1) if rev_prev > 0 else 0,
        "orders_this_week": orders_curr_count, "orders_last_week": orders_prev_count,
        "top_products": [{"name": names_map.get(a, a), "revenue": round(r, 2)} for a, r in top_asins],
        "cancel_rate": health["cancel_rate"],
        "buybox_rate": health["buybox_rate"],
        "low_stock_count": health["low_stock_skus"],
        "stockout_risk_count": health["stockout_risk_count"],
        "avg_sentiment": health["avg_sentiment"],
    }


def collect_pricing_strategy(db, account_ids: list[int]) -> dict:
    price_date = _latest_date(db, account_ids, "price_snapshots", "asin_date")
    price_items = _get_snapshot_items(db, account_ids, "price_snapshots", "asin_date", price_date)

    asins = [s.get("asin", "") for s in price_items]
    names_map = _names(db, account_ids, asins)

    # Sentiment
    insight_date = _latest_date(db, account_ids, "review_insights", "asin_date")
    insight_items = _get_snapshot_items(db, account_ids, "review_insights", "asin_date", insight_date)
    sent_map = {}
    for r in insight_items:
        if r.get("asin"):
            sent_map[r["asin"]] = _dec(r.get("avg_sentiment"))

    # Revenue per ASIN last 30d
    today = date.today()
    month_ago = today - timedelta(days=30)
    orders = _query_orders_in_range(db, account_ids, month_ago, today)
    order_ids = set(o["id"] for o in orders)
    order_items = _query_order_items_for_orders(db, account_ids, order_ids)

    rev_map = defaultdict(float)
    for it in order_items:
        asin = it.get("asin", "")
        price = _dec(it.get("unit_price"))
        qty = int(it.get("quantity_ordered", 0) or 0)
        rev_map[asin] += price * qty

    items = []
    for s in price_items:
        asin = s.get("asin", "")
        items.append({
            "asin": asin, "name": names_map.get(asin, asin),
            "your_price": _dec(s.get("your_price")),
            "buybox_price": _dec(s.get("buybox_price")),
            "lowest_price": _dec(s.get("lowest_price")),
            "is_winner": bool(s.get("is_buybox_winner")),
            "sentiment": sent_map.get(asin),
            "revenue_30d": round(rev_map.get(asin, 0), 2),
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
