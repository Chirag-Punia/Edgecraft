from pydantic import BaseModel
from datetime import datetime

from app.enums import Marketplace, AccountStatus


class MarketplaceCreate(BaseModel):
    marketplace: Marketplace
    credentials: dict | None = None


class MarketplaceResponse(BaseModel):
    id: int
    seller_id: int
    marketplace: Marketplace
    status: AccountStatus
    last_sync_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
