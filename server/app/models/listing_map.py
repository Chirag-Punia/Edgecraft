"""ListingMap table schema (DynamoDB).

Table: listing_map
PK: marketplace_account_id (N)
SK: marketplace_sku (S)

Fields:
    marketplace_account_id: int
    marketplace_sku: str
    product_master_id: int | None
    asin: str | None
    fnsku: str | None
    listing_title: str | None
    listing_status: str | None
    created_at: str (ISO datetime)
    updated_at: str (ISO datetime)
"""
TABLE_NAME = "listing_map"
