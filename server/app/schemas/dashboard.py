from pydantic import BaseModel

from app.enums import ChangeType


class KPIData(BaseModel):
    title: str
    value: str
    change: str
    change_type: ChangeType


class DashboardKPIs(BaseModel):
    kpis: list[KPIData]


# --- Sales Trend ---

class SalesTrendPoint(BaseModel):
    day: str       # YYYY-MM-DD
    gmv: float

class SalesTrendResponse(BaseModel):
    data: list[SalesTrendPoint]


# --- Order Status ---

class OrderStatusItem(BaseModel):
    status: str
    count: int

class OrderStatusResponse(BaseModel):
    data: list[OrderStatusItem]


# --- Top Products ---

class TopProduct(BaseModel):
    asin: str
    title: str
    revenue: float
    units_sold: int

class TopProductsResponse(BaseModel):
    data: list[TopProduct]


# --- Inventory Health ---

class InventoryHealthSummary(BaseModel):
    total_skus: int
    low_stock: int
    healthy: int
    overstocked: int

class InventoryItem(BaseModel):
    seller_sku: str
    asin: str | None
    fulfillable: int
    inbound: int
    total: int

class InventoryHealthResponse(BaseModel):
    summary: InventoryHealthSummary
    flagged_items: list[InventoryItem]


# --- Pricing Overview ---

class PricingLostItem(BaseModel):
    asin: str
    your_price: float
    buybox_price: float
    gap: float

class PricingOverviewResponse(BaseModel):
    total_products: int
    winning_count: int
    win_rate: float
    losing_items: list[PricingLostItem]
