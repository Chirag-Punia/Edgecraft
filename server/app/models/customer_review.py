"""CustomerReview table schema (DynamoDB).

Table: customer_reviews
PK: marketplace_account_id (N)
SK: external_review_id (S)

Fields:
    marketplace_account_id: int
    external_review_id: str
    asin: str | None
    seller_sku: str | None
    rating: int
    title: str | None
    body: str | None
    reviewer_name: str | None
    review_date: str (ISO datetime)
    verified_purchase: bool
    created_at: str (ISO datetime)
"""
TABLE_NAME = "customer_reviews"
