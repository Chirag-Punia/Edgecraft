from datetime import datetime
from pydantic import BaseModel


class SyncTriggerRequest(BaseModel):
    marketplace_account_id: int
    sync_type: str = "full"  # full | orders | inventory | pricing


class SyncRunResponse(BaseModel):
    id: int
    marketplace_account_id: int
    sync_type: str
    status: str
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
