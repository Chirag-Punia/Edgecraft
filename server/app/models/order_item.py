"""OrderItem table schema (DynamoDB).

Table: order_items
PK: id (N) — auto-increment via counters table
GSI: account-index (marketplace_account_id)
GSI: order-index (order_id)

Fields:
    id: int
    order_id: int
    marketplace_account_id: int
    external_order_item_id: str
    asin: str | None
    seller_sku: str | None
    title: str | None
    quantity_ordered: int
    quantity_shipped: int
    unit_price: Decimal
    item_tax: Decimal
    item_discount: Decimal
    created_at: str (ISO datetime)
    updated_at: str (ISO datetime)
"""
TABLE_NAME = "order_items"
