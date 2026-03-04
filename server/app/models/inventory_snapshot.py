from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, UniqueConstraint, func
from app.db.session import Base


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    marketplace_account_id = Column(Integer, ForeignKey("marketplace_accounts.id"), nullable=False, index=True)
    seller_sku = Column(String(100), nullable=False)
    asin = Column(String(20), nullable=True)
    fnsku = Column(String(20), nullable=True)
    fulfillable_quantity = Column(Integer, default=0)
    inbound_quantity = Column(Integer, default=0)
    reserved_quantity = Column(Integer, default=0)
    unfulfillable_quantity = Column(Integer, default=0)
    total_quantity = Column(Integer, default=0)
    snapshot_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("marketplace_account_id", "seller_sku", "snapshot_date", name="uq_inventory_account_sku_date"),
    )
