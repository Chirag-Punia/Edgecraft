"""ProductMaster table schema (DynamoDB).

Table: product_master
PK: seller_id (N)
SK: id (N) — auto-increment via counters table

Fields:
    id: int
    seller_id: int
    name: str
    brand: str | None
    category: str | None
    hsn_code: str | None
    created_at: str (ISO datetime)
    updated_at: str (ISO datetime)
"""
TABLE_NAME = "product_master"
