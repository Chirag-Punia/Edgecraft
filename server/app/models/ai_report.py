"""AIReport table schema (DynamoDB).

Table: ai_reports
PK: seller_id (N)
SK: report_type_lang (S) — composite key "{report_type}#{language}"

Fields:
    seller_id: int
    report_type_lang: str  (composite: "{report_type}#{language}")
    report_type: str
    report_data: dict | None  (JSON-compatible map)
    ai_narrative: str | None
    score: int | None
    generated_at: str | None (ISO datetime)
    expires_at: str | None (ISO datetime)
    language: str  (default: en)
    status: str  (generating | ready | failed)
    created_at: str (ISO datetime)
"""
TABLE_NAME = "ai_reports"
