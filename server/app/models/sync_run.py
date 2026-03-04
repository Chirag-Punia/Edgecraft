from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, func
from app.db.session import Base


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    marketplace_account_id = Column(Integer, ForeignKey("marketplace_accounts.id"), nullable=False, index=True)
    sync_type = Column(String(30), nullable=False)  # full | orders | inventory | pricing
    status = Column(String(20), nullable=False, default="running")  # running | completed | failed
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    records_fetched = Column(Integer, default=0)
    records_upserted = Column(Integer, default=0)
    error_log = Column(Text, nullable=True)
    cursor_state = Column(Text, nullable=True)  # JSON — stores pagination cursor for resumable syncs
