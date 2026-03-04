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
