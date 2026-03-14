"""PricingRecommendation table schema (DynamoDB).

Table: pricing_recommendations
PK: marketplace_account_id (N)
SK: asin_date (S) — composite key "{asin}#{recommendation_date}"

Fields:
    marketplace_account_id: int
    asin_date: str  (composite: "{asin}#{recommendation_date}")
    asin: str
    seller_sku: str | None
    recommendation_date: str (ISO date)
    current_price: Decimal | None
    buybox_price: Decimal | None
    lowest_competitor: Decimal | None
    recommended_price: Decimal | None
    price_action: str | None
    margin_impact_pct: Decimal | None
    reasoning: str | None
    created_at: str (ISO datetime)
"""
TABLE_NAME = "pricing_recommendations"
