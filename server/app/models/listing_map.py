from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, func
from app.db.session import Base


class ListingMap(Base):
    __tablename__ = "listing_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_master_id = Column(Integer, ForeignKey("product_master.id"), nullable=True, index=True)
    marketplace_account_id = Column(Integer, ForeignKey("marketplace_accounts.id"), nullable=False, index=True)
    marketplace_sku = Column(String(100), nullable=False)
    asin = Column(String(20), nullable=True)
    fnsku = Column(String(20), nullable=True)
    listing_title = Column(String(500), nullable=True)
    listing_status = Column(String(30), nullable=True)  # active | inactive | incomplete
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("marketplace_account_id", "marketplace_sku", name="uq_listing_account_sku"),
    )
