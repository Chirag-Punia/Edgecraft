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
    order_count: int = 0

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
    product_name: str | None = None
    fulfillable: int
    inbound: int
    total: int

class InventoryHealthResponse(BaseModel):
    summary: InventoryHealthSummary
    flagged_items: list[InventoryItem]


# --- Pricing Overview ---

class PricingLostItem(BaseModel):
    asin: str
    product_name: str | None = None
    your_price: float
    buybox_price: float
    gap: float

class PricingOverviewResponse(BaseModel):
    total_products: int
    winning_count: int
    win_rate: float
    losing_items: list[PricingLostItem]


# --- Action Items ---

class ActionItem(BaseModel):
    severity: str  # critical / warning / info
    category: str  # inventory / pricing / sentiment / orders
    title: str
    detail: str

class ActionItemsResponse(BaseModel):
    items: list[ActionItem]


# --- Demand Forecast ---

class DemandForecastItem(BaseModel):
    asin: str
    product_name: str
    predicted_units: int
    velocity_7d: float
    days_of_stock: int | None
    stockout_risk: bool

class DemandForecastResponse(BaseModel):
    data: list[DemandForecastItem]


# --- Sentiment Overview ---

class SentimentItem(BaseModel):
    asin: str
    product_name: str
    avg_sentiment: float
    positive: int
    negative: int
    neutral: int
    top_complaints: list[str]

class SentimentOverviewResponse(BaseModel):
    avg_sentiment: float | None
    total_reviews: int
    data: list[SentimentItem]


# --- City Sales ---

class CitySalesItem(BaseModel):
    city: str
    state: str | None
    revenue: float
    order_count: int

class CitySalesResponse(BaseModel):
    data: list[CitySalesItem]
