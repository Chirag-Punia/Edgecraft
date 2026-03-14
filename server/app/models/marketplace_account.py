"""MarketplaceAccount table schema (DynamoDB).

Table: marketplace_accounts
PK: id (N) — auto-increment via counters table
GSI: seller-index (seller_id)

Fields:
    id: int
    seller_id: int
    marketplace: str  (amazon | flipkart | shopify | facebook)
    status: str  (pending | connected | error | disconnected)
    credentials_encrypted: str | None
    last_sync_at: str | None (ISO datetime)
    is_demo_data: bool
    created_at: str (ISO datetime)
    updated_at: str (ISO datetime)
"""
TABLE_NAME = "marketplace_accounts"
