from datetime import datetime
from pydantic import BaseModel

from app.enums import SyncType, SyncRunStatus


class SyncTriggerRequest(BaseModel):
    marketplace_account_id: int
    sync_type: SyncType = SyncType.FULL


class SyncRunResponse(BaseModel):
    id: int
    marketplace_account_id: int
    sync_type: SyncType
    status: SyncRunStatus
    started_at: datetime
    completed_at: datetime | None = None
    records_fetched: int
    records_upserted: int
    error_log: str | None = None

    model_config = {"from_attributes": True}


class SyncTriggerResponse(BaseModel):
    sync_run_id: int
    message: str


class SeedDemoResponse(BaseModel):
    seller_id: int
    marketplace_account_id: int
    sync_run_id: int
    message: str


class UnseedResponse(BaseModel):
    message: str
    records_deleted: int


class DemoStatusResponse(BaseModel):
    is_seeded: bool
