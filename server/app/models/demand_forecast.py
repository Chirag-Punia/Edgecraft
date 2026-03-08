from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Numeric, Boolean, UniqueConstraint, func
from app.db.session import Base


class DemandForecast(Base):
    __tablename__ = "demand_forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    marketplace_account_id = Column(Integer, ForeignKey("marketplace_accounts.id"), nullable=False, index=True)
    asin = Column(String(20), nullable=False)
    seller_sku = Column(String(100), nullable=True)
    forecast_date = Column(Date, nullable=False)
    horizon_days = Column(Integer, nullable=False)
    predicted_units = Column(Integer, nullable=False)
    confidence_lower = Column(Integer, nullable=True)
    confidence_upper = Column(Integer, nullable=True)
    velocity_7d = Column(Numeric(10, 2), nullable=True)
    velocity_30d = Column(Numeric(10, 2), nullable=True)
    days_of_stock = Column(Integer, nullable=True)
    stockout_risk = Column(Boolean, default=False)
    method = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("marketplace_account_id", "asin", "forecast_date", "horizon_days", name="uq_forecast_account_asin_date_horizon"),
    )
