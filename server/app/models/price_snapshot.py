"""PriceSnapshot table schema (DynamoDB).

Table: price_snapshots
PK: marketplace_account_id (N)
SK: asin_date (S) — composite key "{asin}#{snapshot_date}"

Fields:
    marketplace_account_id: int
    asin_date: str  (composite: "{asin}#{snapshot_date}")
    asin: str
    seller_sku: str | None
    your_price: Decimal | None
    landed_price: Decimal | None
    buybox_price: Decimal | None
    lowest_price: Decimal | None
    is_buybox_winner: bool
    snapshot_date: str (ISO date)
    created_at: str (ISO datetime)
"""
TABLE_NAME = "price_snapshots"
