from pydantic import BaseModel


class SellerUpdate(BaseModel):
    business_name: str
    business_type: str | None = None
    primary_category: str | None = None
    gst_number: str | None = None
    city: str | None = None
    state: str | None = None


class SellerResponse(BaseModel):
    id: int
    business_name: str
    business_type: str | None
    primary_category: str | None
    gst_number: str | None
    city: str | None
    state: str | None
    onboarding_completed: bool

    model_config = {"from_attributes": True}
