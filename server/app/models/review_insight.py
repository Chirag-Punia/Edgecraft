from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Numeric, JSON, UniqueConstraint, func
from app.db.session import Base


class ReviewInsight(Base):
    __tablename__ = "review_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    marketplace_account_id = Column(Integer, ForeignKey("marketplace_accounts.id"), nullable=False, index=True)
    asin = Column(String(20), nullable=False, index=True)
    insight_date = Column(Date, nullable=False)
    avg_sentiment = Column(Numeric(3, 2), nullable=True)
    positive_count = Column(Integer, default=0)
    negative_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)
    top_topics = Column(JSON, nullable=True)
    top_complaints = Column(JSON, nullable=True)
    top_praises = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("marketplace_account_id", "asin", "insight_date", name="uq_insight_account_asin_date"),
    )
