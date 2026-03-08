from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, UniqueConstraint, func
from app.db.session import Base


class CustomerReview(Base):
    __tablename__ = "customer_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    marketplace_account_id = Column(Integer, ForeignKey("marketplace_accounts.id"), nullable=False, index=True)
    external_review_id = Column(String(100), nullable=False)
    asin = Column(String(20), nullable=True)
    seller_sku = Column(String(100), nullable=True)
    rating = Column(Integer, nullable=False)
    title = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    reviewer_name = Column(String(255), nullable=True)
    review_date = Column(DateTime, nullable=False, index=True)
    verified_purchase = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("marketplace_account_id", "external_review_id", name="uq_review_account_extid"),
    )
