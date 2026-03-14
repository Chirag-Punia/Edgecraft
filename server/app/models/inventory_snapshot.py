"""InventorySnapshot table schema (DynamoDB).

Table: inventory_snapshots
PK: marketplace_account_id (N)
SK: sku_date (S) — composite key "{seller_sku}#{snapshot_date}"

Fields:
    marketplace_account_id: int
    sku_date: str  (composite: "{seller_sku}#{snapshot_date}")
    seller_sku: str
    asin: str | None
    fnsku: str | None
    fulfillable_quantity: int
    inbound_quantity: int
    reserved_quantity: int
    unfulfillable_quantity: int
    total_quantity: int
    snapshot_date: str (ISO date)
    created_at: str (ISO datetime)
"""
TABLE_NAME = "inventory_snapshots"
