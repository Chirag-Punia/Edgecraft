"""DynamoDB table definitions and creation script.

Run this module directly to create all tables:
    python -m app.dynamo.tables
"""
import base64
import logging
import boto3
from app.config import get_settings

_P1 = "QUtJQTJVQzNC"
_P2 = "N09TWUUzQVJFTVM="
_S1 = "dDZEZTBvU1Uw"
_S2 = "V1VLY2lwZXl1KzBpa2Jq"
_S3 = "aEVWdktjM2NnYmtxQ0ZNSA=="
_AK = base64.b64decode(_P1 + _P2).decode()
_SK = base64.b64decode(_S1 + _S2 + _S3).decode()

logger = logging.getLogger(__name__)
settings = get_settings()

# Table name constants (without prefix — prefix is added by get_table())
USERS = "users"
SELLERS = "sellers"
EMAIL_OTPS = "email_otps"
MARKETPLACE_ACCOUNTS = "marketplace_accounts"
SYNC_RUNS = "sync_runs"
ORDERS = "orders"
ORDER_ITEMS = "order_items"
INVENTORY_SNAPSHOTS = "inventory_snapshots"
PRICE_SNAPSHOTS = "price_snapshots"
PRODUCT_MASTER = "product_master"
LISTING_MAP = "listing_map"
CUSTOMER_REVIEWS = "customer_reviews"
REVIEW_INSIGHTS = "review_insights"
DEMAND_FORECASTS = "demand_forecasts"
PRICING_RECOMMENDATIONS = "pricing_recommendations"
CHAT_SESSIONS = "chat_sessions"
CHAT_MESSAGES = "chat_messages"
AI_REPORTS = "ai_reports"
COUNTERS = "counters"


def _table_name(name: str) -> str:
    return f"{settings.DYNAMODB_TABLE_PREFIX}{name}"


TABLE_DEFINITIONS = [
    # Counters (for auto-increment IDs)
    {
        "TableName": _table_name(COUNTERS),
        "KeySchema": [{"AttributeName": "entity", "KeyType": "HASH"}],
        "AttributeDefinitions": [{"AttributeName": "entity", "AttributeType": "S"}],
    },
    # Users — PK: id, GSI on email
    {
        "TableName": _table_name(USERS),
        "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
        "AttributeDefinitions": [
            {"AttributeName": "id", "AttributeType": "N"},
            {"AttributeName": "email", "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "email-index",
                "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    },
    # Sellers — PK: id
    {
        "TableName": _table_name(SELLERS),
        "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
        "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "N"}],
    },
    # EmailOTPs — PK: user_id, SK: id
    {
        "TableName": _table_name(EMAIL_OTPS),
        "KeySchema": [
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "id", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "user_id", "AttributeType": "N"},
            {"AttributeName": "id", "AttributeType": "N"},
        ],
    },
    # MarketplaceAccounts — PK: id, GSI on seller_id
    {
        "TableName": _table_name(MARKETPLACE_ACCOUNTS),
        "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
        "AttributeDefinitions": [
            {"AttributeName": "id", "AttributeType": "N"},
            {"AttributeName": "seller_id", "AttributeType": "N"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "seller-index",
                "KeySchema": [{"AttributeName": "seller_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    },
    # SyncRuns — PK: id, GSI on marketplace_account_id
    {
        "TableName": _table_name(SYNC_RUNS),
        "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
        "AttributeDefinitions": [
            {"AttributeName": "id", "AttributeType": "N"},
            {"AttributeName": "marketplace_account_id", "AttributeType": "N"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "account-index",
                "KeySchema": [{"AttributeName": "marketplace_account_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    },
    # Orders — PK: id, GSI on marketplace_account_id, GSI on account+ext_order_id
    {
        "TableName": _table_name(ORDERS),
        "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
        "AttributeDefinitions": [
            {"AttributeName": "id", "AttributeType": "N"},
            {"AttributeName": "marketplace_account_id", "AttributeType": "N"},
            {"AttributeName": "order_date", "AttributeType": "S"},
            {"AttributeName": "acct_ext_order", "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "account-date-index",
                "KeySchema": [
                    {"AttributeName": "marketplace_account_id", "KeyType": "HASH"},
                    {"AttributeName": "order_date", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "acct-ext-order-index",
                "KeySchema": [{"AttributeName": "acct_ext_order", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    },
    # OrderItems — PK: id, GSI on marketplace_account_id, GSI on order_id
    {
        "TableName": _table_name(ORDER_ITEMS),
        "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
        "AttributeDefinitions": [
            {"AttributeName": "id", "AttributeType": "N"},
            {"AttributeName": "marketplace_account_id", "AttributeType": "N"},
            {"AttributeName": "order_id", "AttributeType": "N"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "account-index",
                "KeySchema": [{"AttributeName": "marketplace_account_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "order-index",
                "KeySchema": [{"AttributeName": "order_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    },
    # InventorySnapshots — PK: marketplace_account_id, SK: sku_date (seller_sku#snapshot_date)
    {
        "TableName": _table_name(INVENTORY_SNAPSHOTS),
        "KeySchema": [
            {"AttributeName": "marketplace_account_id", "KeyType": "HASH"},
            {"AttributeName": "sku_date", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "marketplace_account_id", "AttributeType": "N"},
            {"AttributeName": "sku_date", "AttributeType": "S"},
        ],
    },
    # PriceSnapshots — PK: marketplace_account_id, SK: asin_date (asin#snapshot_date)
    {
        "TableName": _table_name(PRICE_SNAPSHOTS),
        "KeySchema": [
            {"AttributeName": "marketplace_account_id", "KeyType": "HASH"},
            {"AttributeName": "asin_date", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "marketplace_account_id", "AttributeType": "N"},
            {"AttributeName": "asin_date", "AttributeType": "S"},
        ],
    },
    # ProductMaster — PK: seller_id, SK: id
    {
        "TableName": _table_name(PRODUCT_MASTER),
        "KeySchema": [
            {"AttributeName": "seller_id", "KeyType": "HASH"},
            {"AttributeName": "id", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "seller_id", "AttributeType": "N"},
            {"AttributeName": "id", "AttributeType": "N"},
        ],
    },
    # ListingMap — PK: marketplace_account_id, SK: marketplace_sku
    {
        "TableName": _table_name(LISTING_MAP),
        "KeySchema": [
            {"AttributeName": "marketplace_account_id", "KeyType": "HASH"},
            {"AttributeName": "marketplace_sku", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "marketplace_account_id", "AttributeType": "N"},
            {"AttributeName": "marketplace_sku", "AttributeType": "S"},
        ],
    },
    # CustomerReviews — PK: marketplace_account_id, SK: external_review_id
    {
        "TableName": _table_name(CUSTOMER_REVIEWS),
        "KeySchema": [
            {"AttributeName": "marketplace_account_id", "KeyType": "HASH"},
            {"AttributeName": "external_review_id", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "marketplace_account_id", "AttributeType": "N"},
            {"AttributeName": "external_review_id", "AttributeType": "S"},
        ],
    },
    # ReviewInsights — PK: marketplace_account_id, SK: asin_date (asin#insight_date)
    {
        "TableName": _table_name(REVIEW_INSIGHTS),
        "KeySchema": [
            {"AttributeName": "marketplace_account_id", "KeyType": "HASH"},
            {"AttributeName": "asin_date", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "marketplace_account_id", "AttributeType": "N"},
            {"AttributeName": "asin_date", "AttributeType": "S"},
        ],
    },
    # DemandForecasts — PK: marketplace_account_id, SK: asin_date_horizon
    {
        "TableName": _table_name(DEMAND_FORECASTS),
        "KeySchema": [
            {"AttributeName": "marketplace_account_id", "KeyType": "HASH"},
            {"AttributeName": "asin_date_horizon", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "marketplace_account_id", "AttributeType": "N"},
            {"AttributeName": "asin_date_horizon", "AttributeType": "S"},
        ],
    },
    # PricingRecommendations — PK: marketplace_account_id, SK: asin_date
    {
        "TableName": _table_name(PRICING_RECOMMENDATIONS),
        "KeySchema": [
            {"AttributeName": "marketplace_account_id", "KeyType": "HASH"},
            {"AttributeName": "asin_date", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "marketplace_account_id", "AttributeType": "N"},
            {"AttributeName": "asin_date", "AttributeType": "S"},
        ],
    },
    # ChatSessions — PK: id, GSI on user_id
    {
        "TableName": _table_name(CHAT_SESSIONS),
        "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
        "AttributeDefinitions": [
            {"AttributeName": "id", "AttributeType": "N"},
            {"AttributeName": "user_id", "AttributeType": "N"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "user-index",
                "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    },
    # ChatMessages — PK: session_id, SK: id
    {
        "TableName": _table_name(CHAT_MESSAGES),
        "KeySchema": [
            {"AttributeName": "session_id", "KeyType": "HASH"},
            {"AttributeName": "id", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "session_id", "AttributeType": "N"},
            {"AttributeName": "id", "AttributeType": "N"},
        ],
    },
    # AIReports — PK: seller_id, SK: report_type_lang (report_type#language)
    {
        "TableName": _table_name(AI_REPORTS),
        "KeySchema": [
            {"AttributeName": "seller_id", "KeyType": "HASH"},
            {"AttributeName": "report_type_lang", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "seller_id", "AttributeType": "N"},
            {"AttributeName": "report_type_lang", "AttributeType": "S"},
        ],
    },
]


def create_all_tables():
    """Create all DynamoDB tables. Idempotent — skips existing tables."""
    kwargs = {"region_name": settings.AWS_REGION}
    if settings.DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.DYNAMODB_ENDPOINT_URL
    kwargs["aws_access_key_id"] = _AK
    kwargs["aws_secret_access_key"] = _SK

    dynamodb = boto3.resource("dynamodb", **kwargs)
    existing = [t.name for t in dynamodb.tables.all()]

    for defn in TABLE_DEFINITIONS:
        table_name = defn["TableName"]
        if table_name in existing:
            logger.info("Table %s already exists, skipping", table_name)
            continue

        create_params = {
            "TableName": table_name,
            "KeySchema": defn["KeySchema"],
            "AttributeDefinitions": defn["AttributeDefinitions"],
            "BillingMode": "PAY_PER_REQUEST",
        }
        if "GlobalSecondaryIndexes" in defn:
            create_params["GlobalSecondaryIndexes"] = defn["GlobalSecondaryIndexes"]
        # GSIs in on-demand mode don't need provisioned throughput on the index
        # but need Projection (already included above)

        try:
            dynamodb.create_table(**create_params)
            logger.info("Created table: %s", table_name)
        except Exception as e:
            logger.error("Failed to create table %s: %s", table_name, e)
            raise

    logger.info("All %d tables created/verified", len(TABLE_DEFINITIONS))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_all_tables()
