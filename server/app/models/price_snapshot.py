from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Numeric, Boolean, UniqueConstraint, func
from app.db.session import Base


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    marketplace_account_id = Column(Integer, ForeignKey("marketplace_accounts.id"), nullable=False, index=True)
    asin = Column(String(20), nullable=False)
    seller_sku = Column(String(100), nullable=True)
    your_price = Column(Numeric(10, 2), nullable=True)
    landed_price = Column(Numeric(10, 2), nullable=True)
    buybox_price = Column(Numeric(10, 2), nullable=True)
    lowest_price = Column(Numeric(10, 2), nullable=True)
    is_buybox_winner = Column(Boolean, default=False)
    snapshot_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("marketplace_account_id", "asin", "snapshot_date", name="uq_price_account_asin_date"),
    )
