"""DemandForecast table schema (DynamoDB).

Table: demand_forecasts
PK: marketplace_account_id (N)
SK: asin_date_horizon (S) — composite key "{asin}#{forecast_date}#{horizon_days}"

Fields:
    marketplace_account_id: int
    asin_date_horizon: str  (composite: "{asin}#{forecast_date}#{horizon_days}")
    asin: str
    seller_sku: str | None
    forecast_date: str (ISO date)
    horizon_days: int
    predicted_units: int
    confidence_lower: int | None
    confidence_upper: int | None
    velocity_7d: Decimal | None
    velocity_30d: Decimal | None
    days_of_stock: int | None
    stockout_risk: bool
    method: str | None
    created_at: str (ISO datetime)
"""
TABLE_NAME = "demand_forecasts"
