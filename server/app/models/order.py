"""Order table schema (DynamoDB).

Table: orders
PK: id (N) — auto-increment via counters table
GSI: account-date-index (marketplace_account_id, order_date)
GSI: acct-ext-order-index (acct_ext_order) — composite key "account_id#external_order_id"

Fields:
    id: int
    marketplace_account_id: int
    external_order_id: str
    acct_ext_order: str  (composite: "{marketplace_account_id}#{external_order_id}")
    marketplace: str  (amazon | flipkart | shopify | facebook)
    status: str
    order_date: str (ISO datetime)
    fulfillment_channel: str | None
    currency: str  (default: INR)
    total_amount: Decimal
    shipping_amount: Decimal
    ship_city: str | None
    ship_state: str | None
    raw_payload: str | None
    created_at: str (ISO datetime)
    updated_at: str (ISO datetime)
"""
TABLE_NAME = "orders"
