from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Numeric, UniqueConstraint, func
from app.db.session import Base


class PricingRecommendation(Base):
    __tablename__ = "pricing_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    marketplace_account_id = Column(Integer, ForeignKey("marketplace_accounts.id"), nullable=False, index=True)
    asin = Column(String(20), nullable=False)
    seller_sku = Column(String(100), nullable=True)
    recommendation_date = Column(Date, nullable=False)
    current_price = Column(Numeric(10, 2), nullable=True)
    buybox_price = Column(Numeric(10, 2), nullable=True)
    lowest_competitor = Column(Numeric(10, 2), nullable=True)
    recommended_price = Column(Numeric(10, 2), nullable=True)
    price_action = Column(String(50), nullable=True)
    margin_impact_pct = Column(Numeric(5, 2), nullable=True)
    reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("marketplace_account_id", "asin", "recommendation_date", name="uq_pricing_rec_account_asin_date"),
    )
