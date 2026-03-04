from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric, UniqueConstraint, func
from app.db.session import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    marketplace_account_id = Column(Integer, ForeignKey("marketplace_accounts.id"), nullable=False, index=True)
    external_order_id = Column(String(100), nullable=False)
    marketplace = Column(String(50), nullable=False, default="amazon")
    status = Column(String(50), nullable=False)  # Pending | Shipped | Delivered | Cancelled
    order_date = Column(DateTime, nullable=False, index=True)
    fulfillment_channel = Column(String(20), nullable=True)  # AFN (FBA) | MFN (FBM)
    currency = Column(String(10), default="INR")
    total_amount = Column(Numeric(12, 2), nullable=False)
    shipping_amount = Column(Numeric(10, 2), default=0)
    ship_city = Column(String(100), nullable=True)
    ship_state = Column(String(100), nullable=True)
    raw_payload = Column(Text, nullable=True)  # JSON dump of original API response
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("marketplace_account_id", "external_order_id", name="uq_order_account_extid"),
    )
