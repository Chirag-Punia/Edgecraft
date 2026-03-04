from pydantic import BaseModel
from datetime import datetime


class MarketplaceCreate(BaseModel):
    marketplace: str  # amazon | flipkart | shopify | facebook
    credentials: dict | None = None


class MarketplaceResponse(BaseModel):
    id: int
    seller_id: int
    marketplace: str
    status: str
    last_sync_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
