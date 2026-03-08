"""Deterministic chart data builder — maps report_type to the best chart visualization.

No LLM call needed. Each report_type has a fixed chart mapping.
Returns a ChartData dict that the frontend renders with recharts.
"""

# Brand-consistent color palette
COLORS = {
    "orange": "#F97316",
    "amber": "#F59E0B",
    "blue": "#3B82F6",
    "green": "#22C55E",
    "red": "#EF4444",
    "purple": "#8B5CF6",
    "teal": "#14B8A6",
    "pink": "#EC4899",
}

PALETTE = list(COLORS.values())


def build_chart_data(report_type: str, report_data: dict) -> dict | None:
    """Generate chart configuration from report data.

    Args:
        report_type: The report type string (e.g. "sales_trend").
        report_data: Dict with "columns", "rows", "report_type", "time_range".

    Returns:
        Chart config dict or None if no chart fits.
    """
    rows = report_data.get("rows", [])
    if not rows:
        return None

    builder = _CHART_BUILDERS.get(report_type)
    if not builder:
        return None

    return builder(report_data)


def _sales_trend(data: dict) -> dict:
    return {
        "chart_type": "line",
        "title": f"Sales Trend ({data.get('time_range', '')})",
        "x_key": "day",
        "series": [
            {"name": "GMV (₹)", "data_key": "gmv", "color": COLORS["orange"]},
            {"name": "Orders", "data_key": "order_count", "color": COLORS["blue"]},
        ],
        "x_label": "Date",
        "y_label": "Amount",
        "currency_axis": True,
    }


def _top_products(data: dict) -> dict:
    return {
        "chart_type": "bar",
        "title": "Top Products by Revenue",
        "x_key": "title",
        "series": [
            {"name": "Revenue (₹)", "data_key": "revenue", "color": COLORS["orange"]},
            {"name": "Units Sold", "data_key": "units_sold", "color": COLORS["blue"]},
        ],
        "x_label": "Product",
        "y_label": "Revenue (₹)",
        "currency_axis": True,
    }


def _order_status(data: dict) -> dict:
    return {
        "chart_type": "pie",
        "title": "Orders by Status",
        "x_key": "status",
        "series": [
            {"name": "Orders", "data_key": "count", "color": COLORS["orange"]},
        ],
    }


def _city_wise_sales(data: dict) -> dict:
    return {
        "chart_type": "bar",
        "title": "Sales by City",
        "x_key": "ship_city",
        "series": [
            {"name": "Revenue (₹)", "data_key": "revenue", "color": COLORS["orange"]},
            {"name": "Orders", "data_key": "order_count", "color": COLORS["blue"]},
        ],
        "x_label": "City",
        "y_label": "Revenue (₹)",
        "currency_axis": True,
    }


def _customer_sentiment(data: dict) -> dict:
    return {
        "chart_type": "grouped_bar",
        "title": "Customer Sentiment by Product",
        "x_key": "product_name",
        "series": [
            {"name": "Positive", "data_key": "positive_count", "color": COLORS["green"]},
            {"name": "Neutral", "data_key": "neutral_count", "color": COLORS["amber"]},
            {"name": "Negative", "data_key": "negative_count", "color": COLORS["red"]},
        ],
        "x_label": "Product",
        "y_label": "Review Count",
    }


def _inventory_health(data: dict) -> dict:
    return {
        "chart_type": "stacked_bar",
        "title": "Inventory Breakdown",
        "x_key": "product_name",
        "series": [
            {"name": "Fulfillable", "data_key": "fulfillable_quantity", "color": COLORS["green"]},
            {"name": "Reserved", "data_key": "reserved_quantity", "color": COLORS["amber"]},
            {"name": "Inbound", "data_key": "inbound_quantity", "color": COLORS["blue"]},
            {"name": "Unfulfillable", "data_key": "unfulfillable_quantity", "color": COLORS["red"]},
        ],
        "x_label": "Product",
        "y_label": "Quantity",
    }


def _stockout_risk(data: dict) -> dict:
    return {
        "chart_type": "bar",
        "title": "Stockout Risk — Days of Stock Remaining",
        "x_key": "product_name",
        "series": [
            {"name": "Days of Stock", "data_key": "days_of_stock", "color": COLORS["red"]},
            {"name": "Fulfillable Qty", "data_key": "fulfillable_quantity", "color": COLORS["amber"]},
        ],
        "x_label": "Product",
        "y_label": "Days / Quantity",
    }


def _pricing_analysis(data: dict) -> dict:
    return {
        "chart_type": "grouped_bar",
        "title": "Price Comparison",
        "x_key": "product_name",
        "series": [
            {"name": "Your Price", "data_key": "your_price", "color": COLORS["orange"]},
            {"name": "Buy Box", "data_key": "buybox_price", "color": COLORS["blue"]},
            {"name": "Lowest", "data_key": "lowest_price", "color": COLORS["green"]},
        ],
        "x_label": "Product",
        "y_label": "Price (₹)",
        "currency_axis": True,
    }


def _demand_forecast(data: dict) -> dict:
    return {
        "chart_type": "grouped_bar",
        "title": "Demand Forecast",
        "x_key": "product_name",
        "series": [
            {"name": "Predicted Units", "data_key": "predicted_units", "color": COLORS["orange"]},
            {"name": "7d Velocity", "data_key": "velocity_7d", "color": COLORS["blue"]},
            {"name": "30d Velocity", "data_key": "velocity_30d", "color": COLORS["teal"]},
        ],
        "x_label": "Product",
        "y_label": "Units",
    }


# Mapping of report_type -> chart builder function
# revenue_summary intentionally excluded (single-row aggregate, not chartable)
_CHART_BUILDERS = {
    "sales_trend": _sales_trend,
    "top_products": _top_products,
    "order_status": _order_status,
    "city_wise_sales": _city_wise_sales,
    "customer_sentiment": _customer_sentiment,
    "inventory_health": _inventory_health,
    "stockout_risk": _stockout_risk,
    "pricing_analysis": _pricing_analysis,
    "demand_forecast": _demand_forecast,
}
