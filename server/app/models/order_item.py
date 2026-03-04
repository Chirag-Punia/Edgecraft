from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, UniqueConstraint, func
from app.db.session import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    marketplace_account_id = Column(Integer, ForeignKey("marketplace_accounts.id"), nullable=False, index=True)
    external_order_item_id = Column(String(100), nullable=False)
    asin = Column(String(20), nullable=True)
    seller_sku = Column(String(100), nullable=True)
    title = Column(String(500), nullable=True)
    quantity_ordered = Column(Integer, default=1)
    quantity_shipped = Column(Integer, default=0)
    unit_price = Column(Numeric(10, 2), nullable=False)
    item_tax = Column(Numeric(10, 2), default=0)
    item_discount = Column(Numeric(10, 2), default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("order_id", "external_order_item_id", name="uq_orderitem_order_extid"),
    )
