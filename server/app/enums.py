"""Centralised enums used across models, schemas, and services."""
from enum import Enum


class Marketplace(str, Enum):
    AMAZON = "amazon"
    FLIPKART = "flipkart"
    SHOPIFY = "shopify"
    FACEBOOK = "facebook"


class OrderStatus(str, Enum):
    PENDING = "Pending"
    UNSHIPPED = "Unshipped"
    SHIPPED = "Shipped"
    DELIVERED = "Delivered"
    CANCELLED = "Cancelled"
    CANCELED = "Canceled"       # Amazon uses this spelling


class AccountStatus(str, Enum):
    PENDING = "pending"
    CONNECTED = "connected"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class FulfillmentChannel(str, Enum):
    AFN = "AFN"     # Amazon Fulfillment Network (FBA)
    MFN = "MFN"     # Merchant Fulfilled Network (FBM)


class SyncRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncType(str, Enum):
    FULL = "full"
    ORDERS = "orders"
    INVENTORY = "inventory"
    PRICING = "pricing"


class ChangeType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class ListingStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    INCOMPLETE = "incomplete"


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AIReportType(str, Enum):
    BUSINESS_HEALTH = "business_health"
    PRODUCT_MATRIX = "product_matrix"
    REVENUE_LEAKAGE = "revenue_leakage"
    WEEKLY_DIGEST = "weekly_digest"
    PRICING_STRATEGY = "pricing_strategy"


class AIReportStatus(str, Enum):
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class ReportType(str, Enum):
    TOP_PRODUCTS = "top_products"
    SALES_TREND = "sales_trend"
    REVENUE_SUMMARY = "revenue_summary"
    ORDER_STATUS = "order_status"
    INVENTORY_HEALTH = "inventory_health"
    STOCKOUT_RISK = "stockout_risk"
    PRICING_ANALYSIS = "pricing_analysis"
    CUSTOMER_SENTIMENT = "customer_sentiment"
    DEMAND_FORECAST = "demand_forecast"
    CITY_WISE_SALES = "city_wise_sales"
    WEB_SEARCH = "web_search"
    GENERAL = "general"
