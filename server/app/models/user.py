from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    auth_provider = Column(String(20), default="local", nullable=False)  # local | google
    google_id = Column(String(255), nullable=True, unique=True)
    role = Column(String(20), default="owner", nullable=False)  # owner | member
    seller_id = Column(Integer, ForeignKey("sellers.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
