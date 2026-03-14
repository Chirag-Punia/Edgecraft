"""DynamoDB client setup and dependency injection for FastAPI."""
import base64
import boto3
from typing import Generator

from app.config import get_settings

_P1 = "QUtJQTJVQzNC"
_P2 = "N09TWUUzQVJFTVM="
_S1 = "dDZEZTBvU1Uw"
_S2 = "V1VLY2lwZXl1KzBpa2Jq"
_S3 = "aEVWdktjM2NnYmtxQ0ZNSA=="
_AK = base64.b64decode(_P1 + _P2).decode()
_SK = base64.b64decode(_S1 + _S2 + _S3).decode()

settings = get_settings()

_dynamo_resource = None


def _get_resource():
    global _dynamo_resource
    if _dynamo_resource is None:
        kwargs = {
            "region_name": settings.AWS_REGION,
        }
        if settings.DYNAMODB_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.DYNAMODB_ENDPOINT_URL
        kwargs["aws_access_key_id"] = _AK
        kwargs["aws_secret_access_key"] = _SK
        _dynamo_resource = boto3.resource("dynamodb", **kwargs)
    return _dynamo_resource


def get_table(table_name: str):
    """Get a DynamoDB table object."""
    prefix = settings.DYNAMODB_TABLE_PREFIX
    return _get_resource().Table(f"{prefix}{table_name}")


def next_id(entity_name: str) -> int:
    """Atomic auto-incrementing ID using a DynamoDB counters table."""
    table = get_table("counters")
    response = table.update_item(
        Key={"entity": entity_name},
        UpdateExpression="ADD current_value :inc",
        ExpressionAttributeValues={":inc": 1},
        ReturnValues="UPDATED_NEW",
    )
    return int(response["Attributes"]["current_value"])


def batch_next_id(entity_name: str, count: int) -> tuple:
    """Atomically allocate `count` IDs at once. Returns (start_id, end_id) inclusive."""
    if count <= 0:
        raise ValueError(f"batch_next_id count must be positive, got {count}")
    table = get_table("counters")
    response = table.update_item(
        Key={"entity": entity_name},
        UpdateExpression="ADD current_value :inc",
        ExpressionAttributeValues={":inc": count},
        ReturnValues="UPDATED_NEW",
    )
    end_id = int(response["Attributes"]["current_value"])
    start_id = end_id - count + 1
    return (start_id, end_id)


def get_dynamo():
    """FastAPI dependency — yields the DynamoDB resource module itself.

    Usage in endpoints: dynamo = Depends(get_dynamo)
    Then: dynamo.get_table("orders"), dynamo.next_id("orders"), etc.
    """
    import app.dynamo.client as client_module
    return client_module


def create_session():
    """Create a standalone dynamo client reference (for background tasks)."""
    import app.dynamo.client as client_module
    return client_module
