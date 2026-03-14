"""DynamoDB query templates for the AI assistant.

Replaces SQL templates — each report type becomes a Python function
that queries DynamoDB and aggregates results.
"""
import logging
from collections import defaultdict
from datetime import date, timedelta

from boto3.dynamodb.conditions import Key
from app.dynamo.helpers import query_all, query_by_account_ids

logger = logging.getLogger(__name__)


# ── Shared helpers ────────────────────────────────────────────────

def _query_orders_in_range(db, account_ids, start_date, end_date):
    """Query orders for account_ids within a date range."""
    table = db.get_table("orders")
    orders = []
    for aid in account_ids:
        items = query_all(
            table,
            IndexName="account-date-index",
            KeyConditionExpression=(
                Key("marketplace_account_id").eq(aid)
                & Key("order_date").between(start_date.isoformat(), end_date.isoformat())
            ),
        )
        orders.extend(items)
    return orders


def _query_order_items_for_orders(db, account_ids, order_ids):
    """Query order items for given account_ids, filter by order_ids."""
    if not order_ids:
        return []
    table = db.get_table("order_items")
    order_id_set = set(order_ids)
    items = []
    for aid in account_ids:
        all_items = query_all(
            table,
            IndexName="account-index",
            KeyConditionExpression=Key("marketplace_account_id").eq(aid),
        )
        items.extend([i for i in all_items if i.get("order_id") in order_id_set])
    return items


def _query_snapshots_latest(db, account_ids, table_name, sk_field):
    """Query snapshot table, find latest date, return items for that date.

    sk_field is the sort-key attribute name (e.g. 'sku_date', 'asin_date', 'asin_date_horizon').
    Date is extracted from the sort key by splitting on '#' and finding an ISO date part.
    """
    table = db.get_table(table_name)
    all_items = query_by_account_ids(table, account_ids)
    if not all_items:
        return [], None

    # Extract dates from sort keys
    dates = set()
    for item in all_items:
        sk = item.get(sk_field, "")
        parts = sk.split("#")
        for part in parts:
            try:
                date.fromisoformat(part)
                dates.add(part)
                break
            except (ValueError, TypeError):
                continue

    if not dates:
        return all_items, None

    latest = max(dates)
    # Filter items that have the latest date in their sort key
    filtered = [i for i in all_items if latest in i.get(sk_field, "")]
    return filtered, latest


def _listing_names(db, account_ids, asins):
    """Batch lookup product names from listing_map."""
    if not asins or not account_ids:
        return {}
    table = db.get_table("listing_map")
    asin_set = set(a for a in asins if a)
    lookup = {}
    for aid in account_ids:
        items = query_all(
            table,
            KeyConditionExpression=Key("marketplace_account_id").eq(aid),
        )
        for item in items:
            if item.get("asin") in asin_set and item.get("listing_title"):
                lookup[item["asin"]] = item["listing_title"]
    return {a: lookup.get(a, a or "Unknown") for a in asins}


# ── Report functions ──────────────────────────────────────────────

def _top_products(db, account_ids, params):
    """Top products ranked by revenue or units_sold."""
    start_date = params["start_date"]
    end_date = params["end_date"]
    limit = params.get("limit", 10)
    sort_field = params.get("sort_field", "revenue")
    sort_dir = params.get("sort_dir", "DESC")

    orders = _query_orders_in_range(db, account_ids, start_date, end_date)
    order_ids = [o["id"] for o in orders]
    items = _query_order_items_for_orders(db, account_ids, order_ids)

    # Aggregate by asin
    asin_data = defaultdict(lambda: {"title": None, "revenue": 0.0, "units_sold": 0})
    for it in items:
        asin = it.get("asin", "")
        asin_data[asin]["title"] = asin_data[asin]["title"] or it.get("title")
        price = float(it.get("unit_price", 0) or 0)
        qty = int(it.get("quantity_ordered", 0) or 0)
        asin_data[asin]["revenue"] += price * qty
        asin_data[asin]["units_sold"] += qty

    # Sort
    reverse = sort_dir.upper() != "ASC"
    sorted_items = sorted(
        asin_data.items(),
        key=lambda x: x[1].get(sort_field, 0),
        reverse=reverse,
    )[:limit]

    columns = ["asin", "title", "revenue", "units_sold"]
    rows = [
        [asin, data["title"], round(data["revenue"], 2), data["units_sold"]]
        for asin, data in sorted_items
    ]
    return {"columns": columns, "rows": rows}


def _sales_trend(db, account_ids, params):
    """Daily sales/GMV trend over a time range."""
    start_date = params["start_date"]
    end_date = params["end_date"]

    orders = _query_orders_in_range(db, account_ids, start_date, end_date)

    daily = defaultdict(lambda: {"gmv": 0.0, "order_count": 0})
    for o in orders:
        order_date_str = str(o.get("order_date", ""))[:10]  # YYYY-MM-DD
        daily[order_date_str]["gmv"] += float(o.get("total_amount", 0) or 0)
        daily[order_date_str]["order_count"] += 1

    columns = ["day", "gmv", "order_count"]
    rows = sorted(
        [[day, round(d["gmv"], 2), d["order_count"]] for day, d in daily.items()],
        key=lambda x: x[0],
    )
    return {"columns": columns, "rows": rows}


def _revenue_summary(db, account_ids, params):
    """Total revenue, orders, units for a time range."""
    start_date = params["start_date"]
    end_date = params["end_date"]

    orders = _query_orders_in_range(db, account_ids, start_date, end_date)
    order_ids = [o["id"] for o in orders]
    items = _query_order_items_for_orders(db, account_ids, order_ids)

    total_revenue = sum(float(o.get("total_amount", 0) or 0) for o in orders)
    total_orders = len(orders)
    total_units = sum(int(it.get("quantity_ordered", 0) or 0) for it in items)
    avg_order_value = round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0

    columns = ["total_revenue", "total_orders", "total_units", "avg_order_value"]
    rows = [[round(total_revenue, 2), total_orders, total_units, avg_order_value]]
    return {"columns": columns, "rows": rows}


def _order_status(db, account_ids, params):
    """Order count by status."""
    start_date = params["start_date"]
    end_date = params["end_date"]

    orders = _query_orders_in_range(db, account_ids, start_date, end_date)

    status_counts = defaultdict(int)
    for o in orders:
        status_counts[o.get("status", "Unknown")] += 1

    columns = ["status", "count"]
    rows = sorted(
        [[status, count] for status, count in status_counts.items()],
        key=lambda x: x[1],
        reverse=True,
    )
    return {"columns": columns, "rows": rows}


def _inventory_health(db, account_ids, params):
    """Current inventory status for all SKUs."""
    snapshot_date = params.get("snapshot_date")
    limit = params.get("limit", 10)

    items, latest = _query_snapshots_latest(db, account_ids, "inventory_snapshots", "sku_date")
    if snapshot_date:
        sd = snapshot_date.isoformat() if isinstance(snapshot_date, date) else str(snapshot_date)
        items = [i for i in items if sd in i.get("sku_date", "")]
        if not items:
            # Fall back to latest
            items, latest = _query_snapshots_latest(db, account_ids, "inventory_snapshots", "sku_date")

    # Lookup names
    asins = list(set(i.get("asin", "") for i in items if i.get("asin")))
    names = _listing_names(db, account_ids, asins)

    # Sort by fulfillable_quantity ASC
    items.sort(key=lambda x: int(x.get("fulfillable_quantity", 0) or 0))
    items = items[:limit]

    columns = ["seller_sku", "asin", "product_name", "fulfillable_quantity", "inbound_quantity",
               "reserved_quantity", "unfulfillable_quantity", "total_quantity"]
    rows = [
        [
            i.get("seller_sku", ""),
            i.get("asin", ""),
            names.get(i.get("asin", ""), i.get("asin", "")),
            int(i.get("fulfillable_quantity", 0) or 0),
            int(i.get("inbound_quantity", 0) or 0),
            int(i.get("reserved_quantity", 0) or 0),
            int(i.get("unfulfillable_quantity", 0) or 0),
            int(i.get("total_quantity", 0) or 0),
        ]
        for i in items
    ]
    return {"columns": columns, "rows": rows}


def _stockout_risk(db, account_ids, params):
    """Products at risk of stocking out (low fulfillable quantity)."""
    threshold = params.get("threshold", 10)
    limit = params.get("limit", 10)

    inv_items, inv_latest = _query_snapshots_latest(db, account_ids, "inventory_snapshots", "sku_date")
    fc_items, _ = _query_snapshots_latest(db, account_ids, "demand_forecasts", "asin_date_horizon")

    # Filter demand forecasts to horizon_days=7
    fc_map = {}
    for f in fc_items:
        if int(f.get("horizon_days", 0)) == 7:
            fc_map[f.get("asin", "")] = f

    # Filter low stock
    low_stock = [i for i in inv_items if int(i.get("fulfillable_quantity", 0) or 0) <= threshold]
    low_stock.sort(key=lambda x: int(x.get("fulfillable_quantity", 0) or 0))
    low_stock = low_stock[:limit]

    asins = list(set(i.get("asin", "") for i in low_stock if i.get("asin")))
    names = _listing_names(db, account_ids, asins)

    columns = ["seller_sku", "asin", "product_name", "fulfillable_quantity", "total_quantity",
               "velocity_7d", "days_of_stock", "predicted_demand_7d"]
    rows = []
    for i in low_stock:
        asin = i.get("asin", "")
        fc = fc_map.get(asin, {})
        rows.append([
            i.get("seller_sku", ""),
            asin,
            names.get(asin, asin),
            int(i.get("fulfillable_quantity", 0) or 0),
            int(i.get("total_quantity", 0) or 0),
            float(fc.get("velocity_7d", 0) or 0),
            fc.get("days_of_stock"),
            fc.get("predicted_units"),
        ])
    return {"columns": columns, "rows": rows}


def _pricing_analysis(db, account_ids, params):
    """Pricing comparison: your price vs buybox vs lowest."""
    limit = params.get("limit", 10)

    price_items, _ = _query_snapshots_latest(db, account_ids, "price_snapshots", "asin_date")
    rec_items, _ = _query_snapshots_latest(db, account_ids, "pricing_recommendations", "asin_date")

    # Build recommendation map by asin
    rec_map = {}
    for r in rec_items:
        rec_map[r.get("asin", "")] = r

    asins = list(set(i.get("asin", "") for i in price_items if i.get("asin")))
    names = _listing_names(db, account_ids, asins)

    # Sort: non-winners first, then by price gap desc
    def sort_key(item):
        is_winner = 1 if item.get("is_buybox_winner") else 0
        your_price = float(item.get("your_price", 0) or 0)
        buybox_price = float(item.get("buybox_price", 0) or 0)
        gap = your_price - buybox_price
        return (is_winner, -gap)

    price_items.sort(key=sort_key)
    price_items = price_items[:limit]

    columns = ["asin", "seller_sku", "product_name", "your_price", "buybox_price", "lowest_price",
               "is_buybox_winner", "recommended_price", "price_action", "reasoning"]
    rows = []
    for p in price_items:
        asin = p.get("asin", "")
        rec = rec_map.get(asin, {})
        rows.append([
            asin,
            p.get("seller_sku", ""),
            names.get(asin, asin),
            float(p.get("your_price", 0) or 0),
            float(p.get("buybox_price", 0) or 0),
            float(p.get("lowest_price", 0) or 0),
            bool(p.get("is_buybox_winner")),
            float(rec.get("recommended_price", 0) or 0) if rec.get("recommended_price") else None,
            rec.get("price_action"),
            rec.get("reasoning"),
        ])
    return {"columns": columns, "rows": rows}


def _customer_sentiment(db, account_ids, params):
    """Customer review sentiment by product."""
    limit = params.get("limit", 10)

    items, _ = _query_snapshots_latest(db, account_ids, "review_insights", "asin_date")

    asins = list(set(i.get("asin", "") for i in items if i.get("asin")))
    names = _listing_names(db, account_ids, asins)

    # Sort by avg_sentiment ASC
    items.sort(key=lambda x: float(x.get("avg_sentiment", 0) or 0))
    items = items[:limit]

    columns = ["asin", "product_name", "avg_sentiment", "positive_count", "negative_count",
               "neutral_count", "top_topics", "top_complaints", "top_praises", "summary"]
    rows = [
        [
            i.get("asin", ""),
            names.get(i.get("asin", ""), i.get("asin", "")),
            float(i.get("avg_sentiment", 0) or 0),
            int(i.get("positive_count", 0) or 0),
            int(i.get("negative_count", 0) or 0),
            int(i.get("neutral_count", 0) or 0),
            i.get("top_topics", []),
            i.get("top_complaints", []),
            i.get("top_praises", []),
            i.get("summary", ""),
        ]
        for i in items
    ]
    return {"columns": columns, "rows": rows}


def _demand_forecast(db, account_ids, params):
    """Demand forecast for products."""
    horizon_days = params.get("horizon_days", 7)
    limit = params.get("limit", 10)

    items, _ = _query_snapshots_latest(db, account_ids, "demand_forecasts", "asin_date_horizon")

    # Filter by horizon_days
    items = [i for i in items if int(i.get("horizon_days", 0)) == horizon_days]

    asins = list(set(i.get("asin", "") for i in items if i.get("asin")))
    names = _listing_names(db, account_ids, asins)

    # Sort: stockout_risk desc, days_of_stock asc
    items.sort(key=lambda x: (
        -(1 if x.get("stockout_risk") else 0),
        int(x.get("days_of_stock", 9999) or 9999),
    ))
    items = items[:limit]

    columns = ["asin", "seller_sku", "product_name", "predicted_units", "velocity_7d", "velocity_30d",
               "days_of_stock", "stockout_risk", "confidence_lower", "confidence_upper", "method"]
    rows = [
        [
            i.get("asin", ""),
            i.get("seller_sku", ""),
            names.get(i.get("asin", ""), i.get("asin", "")),
            int(i.get("predicted_units", 0) or 0),
            float(i.get("velocity_7d", 0) or 0),
            float(i.get("velocity_30d", 0) or 0),
            i.get("days_of_stock"),
            bool(i.get("stockout_risk")),
            float(i.get("confidence_lower", 0) or 0) if i.get("confidence_lower") is not None else None,
            float(i.get("confidence_upper", 0) or 0) if i.get("confidence_upper") is not None else None,
            i.get("method", ""),
        ]
        for i in items
    ]
    return {"columns": columns, "rows": rows}


def _city_wise_sales(db, account_ids, params):
    """Sales breakdown by city/state."""
    start_date = params["start_date"]
    end_date = params["end_date"]
    limit = params.get("limit", 10)

    orders = _query_orders_in_range(db, account_ids, start_date, end_date)

    city_data = defaultdict(lambda: {"state": None, "order_count": 0, "revenue": 0.0})
    for o in orders:
        city = o.get("ship_city")
        if not city:
            continue
        city_data[city]["state"] = city_data[city]["state"] or o.get("ship_state")
        city_data[city]["order_count"] += 1
        city_data[city]["revenue"] += float(o.get("total_amount", 0) or 0)

    columns = ["ship_city", "ship_state", "order_count", "revenue"]
    rows = sorted(
        [
            [city, d["state"], d["order_count"], round(d["revenue"], 2)]
            for city, d in city_data.items()
        ],
        key=lambda x: x[3],
        reverse=True,
    )[:limit]
    return {"columns": columns, "rows": rows}


# ── Template registry ─────────────────────────────────────────────

TEMPLATES = {
    "top_products": {
        "fn": _top_products,
        "columns": ["asin", "title", "revenue", "units_sold"],
        "default_sort_field": "revenue",
        "allowed_sort_fields": ["revenue", "units_sold"],
    },
    "sales_trend": {
        "fn": _sales_trend,
        "columns": ["day", "gmv", "order_count"],
    },
    "revenue_summary": {
        "fn": _revenue_summary,
        "columns": ["total_revenue", "total_orders", "total_units", "avg_order_value"],
    },
    "order_status": {
        "fn": _order_status,
        "columns": ["status", "count"],
    },
    "inventory_health": {
        "fn": _inventory_health,
        "columns": ["seller_sku", "asin", "product_name", "fulfillable_quantity", "inbound_quantity",
                     "reserved_quantity", "unfulfillable_quantity", "total_quantity"],
    },
    "stockout_risk": {
        "fn": _stockout_risk,
        "columns": ["seller_sku", "asin", "product_name", "fulfillable_quantity", "total_quantity",
                     "velocity_7d", "days_of_stock", "predicted_demand_7d"],
    },
    "pricing_analysis": {
        "fn": _pricing_analysis,
        "columns": ["asin", "seller_sku", "product_name", "your_price", "buybox_price", "lowest_price",
                     "is_buybox_winner", "recommended_price", "price_action", "reasoning"],
    },
    "customer_sentiment": {
        "fn": _customer_sentiment,
        "columns": ["asin", "product_name", "avg_sentiment", "positive_count", "negative_count",
                     "neutral_count", "top_topics", "top_complaints", "top_praises", "summary"],
    },
    "demand_forecast": {
        "fn": _demand_forecast,
        "columns": ["asin", "seller_sku", "product_name", "predicted_units", "velocity_7d", "velocity_30d",
                     "days_of_stock", "stockout_risk", "confidence_lower", "confidence_upper", "method"],
    },
    "city_wise_sales": {
        "fn": _city_wise_sales,
        "columns": ["ship_city", "ship_state", "order_count", "revenue"],
    },
}


# Schema catalog for the LLM system prompt — describes available tables and columns
SCHEMA_CATALOG = """
Available tables and columns:
- orders: id, marketplace_account_id, external_order_id, status (Pending/Unshipped/Shipped/Delivered/Cancelled), order_date, fulfillment_channel (AFN/MFN), currency (INR), total_amount, shipping_amount, ship_city, ship_state
- order_items: id, order_id, marketplace_account_id, asin, seller_sku, title, quantity_ordered, quantity_shipped, unit_price, item_tax, item_discount
- inventory_snapshots: id, marketplace_account_id, seller_sku, asin, fulfillable_quantity, inbound_quantity, reserved_quantity, unfulfillable_quantity, total_quantity, snapshot_date
- price_snapshots: id, marketplace_account_id, asin, seller_sku, your_price, buybox_price, lowest_price, is_buybox_winner, snapshot_date
- customer_reviews: id, marketplace_account_id, asin, rating (1-5), title, body, reviewer_name, review_date, verified_purchase
- review_insights: id, marketplace_account_id, asin, insight_date, avg_sentiment (-1 to 1), positive_count, negative_count, neutral_count, top_topics (JSON), top_complaints (JSON), top_praises (JSON), summary
- demand_forecasts: marketplace_account_id, asin, seller_sku, forecast_date, horizon_days (7/14/30), predicted_units, velocity_7d, velocity_30d, days_of_stock, stockout_risk (bool), method
- pricing_recommendations: marketplace_account_id, asin, recommendation_date, current_price, buybox_price, lowest_competitor, recommended_price, price_action (reduce/hold/increase), margin_impact_pct, reasoning
"""
