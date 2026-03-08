"""Pre-defined parameterized SQL templates for the AI assistant.

The LLM never generates raw SQL. Instead, it produces a ReportSpec JSON
that maps to one of these pre-approved templates. All user-influenced values
are bound parameters — never interpolated.
"""
from sqlalchemy import text


TEMPLATES = {
    "top_products": {
        "description": "Top products ranked by a metric (revenue, units_sold)",
        "sql": text("""
            SELECT oi.asin, oi.title,
                   SUM(oi.unit_price * oi.quantity_ordered) AS revenue,
                   SUM(oi.quantity_ordered) AS units_sold
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            WHERE o.marketplace_account_id IN :account_ids
              AND o.order_date >= :start_date
              AND o.order_date <= :end_date
            GROUP BY oi.asin, oi.title
            ORDER BY {sort_field} {sort_dir}
            LIMIT :limit
        """),
        "default_sort_field": "revenue",
        "allowed_sort_fields": ["revenue", "units_sold"],
        "columns": ["asin", "title", "revenue", "units_sold"],
    },

    "sales_trend": {
        "description": "Daily sales/GMV trend over a time range",
        "sql": text("""
            SELECT DATE(o.order_date) AS day,
                   COALESCE(SUM(o.total_amount), 0) AS gmv,
                   COUNT(o.id) AS order_count
            FROM orders o
            WHERE o.marketplace_account_id IN :account_ids
              AND o.order_date >= :start_date
              AND o.order_date <= :end_date
            GROUP BY DATE(o.order_date)
            ORDER BY day ASC
        """),
        "columns": ["day", "gmv", "order_count"],
    },

    "revenue_summary": {
        "description": "Total revenue, orders, units for a time range",
        "sql": text("""
            SELECT COALESCE(SUM(o.total_amount), 0) AS total_revenue,
                   COUNT(DISTINCT o.id) AS total_orders,
                   COALESCE(SUM(oi.quantity_ordered), 0) AS total_units,
                   COALESCE(AVG(o.total_amount), 0) AS avg_order_value
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            WHERE o.marketplace_account_id IN :account_ids
              AND o.order_date >= :start_date
              AND o.order_date <= :end_date
        """),
        "columns": ["total_revenue", "total_orders", "total_units", "avg_order_value"],
    },

    "order_status": {
        "description": "Order count by status",
        "sql": text("""
            SELECT o.status, COUNT(o.id) AS count
            FROM orders o
            WHERE o.marketplace_account_id IN :account_ids
              AND o.order_date >= :start_date
              AND o.order_date <= :end_date
            GROUP BY o.status
            ORDER BY count DESC
        """),
        "columns": ["status", "count"],
    },

    "inventory_health": {
        "description": "Current inventory status for all SKUs",
        "sql": text("""
            SELECT i.seller_sku, i.asin,
                   (SELECT lm.listing_title FROM listing_map lm
                    WHERE lm.marketplace_account_id = i.marketplace_account_id
                    AND lm.asin = i.asin LIMIT 1) AS product_name,
                   i.fulfillable_quantity, i.inbound_quantity,
                   i.reserved_quantity, i.unfulfillable_quantity,
                   i.total_quantity
            FROM inventory_snapshots i
            WHERE i.marketplace_account_id IN :account_ids
              AND i.snapshot_date = :snapshot_date
            ORDER BY i.fulfillable_quantity ASC
            LIMIT :limit
        """),
        "columns": ["seller_sku", "asin", "product_name", "fulfillable_quantity", "inbound_quantity",
                     "reserved_quantity", "unfulfillable_quantity", "total_quantity"],
    },

    "stockout_risk": {
        "description": "Products at risk of stocking out (low fulfillable quantity)",
        "sql": text("""
            SELECT i.seller_sku, i.asin,
                   (SELECT lm.listing_title FROM listing_map lm
                    WHERE lm.marketplace_account_id = i.marketplace_account_id
                    AND lm.asin = i.asin LIMIT 1) AS product_name,
                   i.fulfillable_quantity,
                   i.total_quantity,
                   df.velocity_7d,
                   df.days_of_stock,
                   df.predicted_units AS predicted_demand_7d
            FROM inventory_snapshots i
            LEFT JOIN demand_forecasts df
              ON df.marketplace_account_id = i.marketplace_account_id
              AND df.asin = i.asin
              AND df.forecast_date = :snapshot_date
              AND df.horizon_days = 7
            WHERE i.marketplace_account_id IN :account_ids
              AND i.snapshot_date = :snapshot_date
              AND i.fulfillable_quantity <= :threshold
            ORDER BY i.fulfillable_quantity ASC
            LIMIT :limit
        """),
        "columns": ["seller_sku", "asin", "product_name", "fulfillable_quantity", "total_quantity",
                     "velocity_7d", "days_of_stock", "predicted_demand_7d"],
    },

    "pricing_analysis": {
        "description": "Pricing comparison: your price vs buybox vs lowest",
        "sql": text("""
            SELECT p.asin, p.seller_sku,
                   (SELECT lm.listing_title FROM listing_map lm
                    WHERE lm.marketplace_account_id = p.marketplace_account_id
                    AND lm.asin = p.asin LIMIT 1) AS product_name,
                   p.your_price, p.buybox_price, p.lowest_price,
                   p.is_buybox_winner,
                   pr.recommended_price, pr.price_action, pr.reasoning
            FROM price_snapshots p
            LEFT JOIN pricing_recommendations pr
              ON pr.marketplace_account_id = p.marketplace_account_id
              AND pr.asin = p.asin
              AND pr.recommendation_date = p.snapshot_date
            WHERE p.marketplace_account_id IN :account_ids
              AND p.snapshot_date = :snapshot_date
            ORDER BY p.is_buybox_winner ASC, (p.your_price - p.buybox_price) DESC
            LIMIT :limit
        """),
        "columns": ["asin", "seller_sku", "product_name", "your_price", "buybox_price", "lowest_price",
                     "is_buybox_winner", "recommended_price", "price_action", "reasoning"],
    },

    "customer_sentiment": {
        "description": "Customer review sentiment by product",
        "sql": text("""
            SELECT ri.asin,
                   (SELECT lm.listing_title FROM listing_map lm
                    WHERE lm.marketplace_account_id = ri.marketplace_account_id
                    AND lm.asin = ri.asin LIMIT 1) AS product_name,
                   ri.avg_sentiment,
                   ri.positive_count, ri.negative_count, ri.neutral_count,
                   ri.top_topics, ri.top_complaints, ri.top_praises,
                   ri.summary
            FROM review_insights ri
            WHERE ri.marketplace_account_id IN :account_ids
              AND ri.insight_date = :snapshot_date
            ORDER BY ri.avg_sentiment ASC
            LIMIT :limit
        """),
        "columns": ["asin", "product_name", "avg_sentiment", "positive_count", "negative_count",
                     "neutral_count", "top_topics", "top_complaints", "top_praises", "summary"],
    },

    "demand_forecast": {
        "description": "Demand forecast for products",
        "sql": text("""
            SELECT df.asin, df.seller_sku,
                   (SELECT lm.listing_title FROM listing_map lm
                    WHERE lm.marketplace_account_id = df.marketplace_account_id
                    AND lm.asin = df.asin LIMIT 1) AS product_name,
                   df.predicted_units, df.velocity_7d, df.velocity_30d,
                   df.days_of_stock, df.stockout_risk,
                   df.confidence_lower, df.confidence_upper,
                   df.method
            FROM demand_forecasts df
            WHERE df.marketplace_account_id IN :account_ids
              AND df.forecast_date = :snapshot_date
              AND df.horizon_days = :horizon_days
            ORDER BY df.stockout_risk DESC, df.days_of_stock ASC
            LIMIT :limit
        """),
        "columns": ["asin", "seller_sku", "product_name", "predicted_units", "velocity_7d", "velocity_30d",
                     "days_of_stock", "stockout_risk", "confidence_lower", "confidence_upper", "method"],
    },

    "city_wise_sales": {
        "description": "Sales breakdown by city/state",
        "sql": text("""
            SELECT o.ship_city, o.ship_state,
                   COUNT(o.id) AS order_count,
                   COALESCE(SUM(o.total_amount), 0) AS revenue
            FROM orders o
            WHERE o.marketplace_account_id IN :account_ids
              AND o.order_date >= :start_date
              AND o.order_date <= :end_date
              AND o.ship_city IS NOT NULL
            GROUP BY o.ship_city, o.ship_state
            ORDER BY revenue DESC
            LIMIT :limit
        """),
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
