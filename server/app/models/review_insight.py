"""ReviewInsight table schema (DynamoDB).

Table: review_insights
PK: marketplace_account_id (N)
SK: asin_date (S) — composite key "{asin}#{insight_date}"

Fields:
    marketplace_account_id: int
    asin_date: str  (composite: "{asin}#{insight_date}")
    asin: str
    insight_date: str (ISO date)
    avg_sentiment: Decimal | None
    positive_count: int
    negative_count: int
    neutral_count: int
    top_topics: list | None  (JSON-compatible list)
    top_complaints: list | None  (JSON-compatible list)
    top_praises: list | None  (JSON-compatible list)
    summary: str | None
    created_at: str (ISO datetime)
"""
TABLE_NAME = "review_insights"
