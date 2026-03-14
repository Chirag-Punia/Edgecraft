"""Seller table schema (DynamoDB).

Table: sellers
PK: id (N) — auto-increment via counters table

Fields:
    id: int
    business_name: str
    business_type: str | None
    primary_category: str | None
    gst_number: str | None
    city: str | None
    state: str | None
    onboarding_completed: bool
    created_at: str (ISO datetime)
    updated_at: str (ISO datetime)
"""
TABLE_NAME = "sellers"
