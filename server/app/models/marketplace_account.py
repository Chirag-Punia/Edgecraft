from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, func
from app.db.session import Base


class MarketplaceAccount(Base):
    __tablename__ = "marketplace_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(Integer, ForeignKey("sellers.id"), nullable=False, index=True)
    marketplace = Column(String(50), nullable=False)  # amazon | flipkart | shopify | facebook
    status = Column(String(30), default="pending", nullable=False)  # pending | connected | error | disconnected
    credentials_encrypted = Column(Text, nullable=True)
    last_sync_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
