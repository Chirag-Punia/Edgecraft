"""User table schema (DynamoDB).

Table: users
PK: id (N) — auto-increment via counters table
GSI: email-index (email)

Fields:
    id: int
    email: str
    hashed_password: str | None
    full_name: str
    is_email_verified: bool
    auth_provider: str  (local | google)
    google_id: str | None
    role: str  (owner | member)
    seller_id: int | None
    created_at: str (ISO datetime)
    updated_at: str (ISO datetime)
"""
TABLE_NAME = "users"
