from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from app.db.session import Base


class ProductMaster(Base):
    __tablename__ = "product_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(Integer, ForeignKey("sellers.id"), nullable=False, index=True)
    name = Column(String(500), nullable=False)
    brand = Column(String(255), nullable=True)
    category = Column(String(255), nullable=True)
    hsn_code = Column(String(20), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
