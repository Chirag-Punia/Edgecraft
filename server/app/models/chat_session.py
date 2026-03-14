"""ChatSession table schema (DynamoDB).

Table: chat_sessions
PK: id (N) — auto-increment via counters table
GSI: user-index (user_id)

Fields:
    id: int
    seller_id: int
    user_id: int
    title: str | None
    language: str  (default: en)
    created_at: str (ISO datetime)
    updated_at: str (ISO datetime)
"""
TABLE_NAME = "chat_sessions"
