"""ChatMessage table schema (DynamoDB).

Table: chat_messages
PK: session_id (N)
SK: id (N) — auto-increment via counters table

Fields:
    id: int
    session_id: int
    role: str  (user | assistant | system)
    content: str
    report_spec: dict | None  (JSON-compatible map)
    report_data: dict | None  (JSON-compatible map)
    metadata: dict | None  (JSON-compatible map)
    created_at: str (ISO datetime)
"""
TABLE_NAME = "chat_messages"
