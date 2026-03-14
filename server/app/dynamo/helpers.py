"""DynamoDB query helpers — pagination, batch operations, aggregation utilities."""
from datetime import datetime, date
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Key, Attr


def _convert_list_item(v):
    """Recursively convert a list element for DynamoDB compatibility."""
    if isinstance(v, dict):
        return to_dynamo_item(v)
    if isinstance(v, float):
        return Decimal(str(v))
    if isinstance(v, list):
        return [_convert_list_item(i) for i in v]
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def to_dynamo_item(data: dict) -> dict:
    """Convert a Python dict to DynamoDB-compatible item.

    - Converts float to Decimal
    - Converts date/datetime to ISO string
    - Removes None values (DynamoDB doesn't support None for non-existent attributes)
    - Converts empty strings to None removal
    """
    item = {}
    for k, v in data.items():
        if v is None:
            continue
        if isinstance(v, float):
            item[k] = Decimal(str(v))
        elif isinstance(v, datetime):
            item[k] = v.isoformat()
        elif isinstance(v, date):
            item[k] = v.isoformat()
        elif isinstance(v, dict):
            item[k] = to_dynamo_item(v)
        elif isinstance(v, list):
            item[k] = [_convert_list_item(i) for i in v]
        elif isinstance(v, bool):
            item[k] = v
        else:
            item[k] = v
    return item


def from_dynamo_item(item: dict) -> dict:
    """Convert a DynamoDB item back to regular Python types.

    - Converts Decimal to float or int
    """
    result = {}
    for k, v in item.items():
        if isinstance(v, Decimal):
            if v == int(v):
                result[k] = int(v)
            else:
                result[k] = float(v)
        elif isinstance(v, dict):
            result[k] = from_dynamo_item(v)
        elif isinstance(v, list):
            result[k] = [from_dynamo_item(i) if isinstance(i, dict) else (float(i) if isinstance(i, Decimal) else i) for i in v]
        else:
            result[k] = v
    return result


def query_all(table, **kwargs) -> list[dict]:
    """Query a DynamoDB table with automatic pagination. Returns all items."""
    items = []
    response = table.query(**kwargs)
    items.extend(response.get("Items", []))
    while response.get("LastEvaluatedKey"):
        kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        response = table.query(**kwargs)
        items.extend(response.get("Items", []))
    return [from_dynamo_item(item) for item in items]


def scan_all(table, **kwargs) -> list[dict]:
    """Scan a DynamoDB table with automatic pagination. Returns all items."""
    items = []
    response = table.scan(**kwargs)
    items.extend(response.get("Items", []))
    while response.get("LastEvaluatedKey"):
        kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        response = table.scan(**kwargs)
        items.extend(response.get("Items", []))
    return [from_dynamo_item(item) for item in items]


def query_by_account_ids(table, account_ids: list[int], extra_filter=None, index_name=None) -> list[dict]:
    """Query items across multiple marketplace_account_ids (partition keys).

    DynamoDB doesn't support IN clause for partition keys, so we query each separately and merge.
    """
    all_items = []
    for account_id in account_ids:
        kwargs = {
            "KeyConditionExpression": Key("marketplace_account_id").eq(account_id),
        }
        if index_name:
            kwargs["IndexName"] = index_name
        if extra_filter:
            kwargs["FilterExpression"] = extra_filter
        all_items.extend(query_all(table, **kwargs))
    return all_items


def batch_get_items(table, keys: list[dict]) -> list[dict]:
    """Batch get items from a table. Handles pagination for >100 keys."""
    items = []
    table_name = table.table_name
    resource = table.meta.client.meta.service_model
    # Use the table resource for batch operations
    dynamo_resource = table.meta.client

    for i in range(0, len(keys), 100):
        batch = keys[i:i + 100]
        response = dynamo_resource.batch_get_item(
            RequestItems={table_name: {"Keys": batch}}
        )
        items.extend(response.get("Responses", {}).get(table_name, []))
    return [from_dynamo_item(item) for item in items]


def batch_write_items(table, items: list[dict]):
    """Batch write items to a table. Handles DynamoDB 25-item batch limit."""
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)


def batch_delete_items(table, keys: list[dict]):
    """Batch delete items from a table. Handles DynamoDB 25-item batch limit."""
    with table.batch_writer() as batch:
        for key in keys:
            batch.delete_item(Key=key)


def now_iso() -> str:
    """Current UTC datetime as ISO string."""
    return datetime.utcnow().isoformat()


def today_iso() -> str:
    """Current date as ISO string."""
    return date.today().isoformat()
