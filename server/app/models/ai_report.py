from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, UniqueConstraint, func
from app.db.session import Base


class AIReport(Base):
    __tablename__ = "ai_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(Integer, ForeignKey("sellers.id"), nullable=False, index=True)
    report_type = Column(String(50), nullable=False)
    report_data = Column(JSON, nullable=True)
    ai_narrative = Column(Text, nullable=True)
    score = Column(Integer, nullable=True)
    generated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    language = Column(String(5), nullable=False, default="en")
    status = Column(String(20), nullable=False, default="generating")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("seller_id", "report_type", "language", name="uq_ai_report_seller_type_lang"),
    )
