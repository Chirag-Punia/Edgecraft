from types import SimpleNamespace
from fastapi import HTTPException, status
from app.dynamo.helpers import to_dynamo_item, from_dynamo_item, now_iso


def get_seller(db, user):
    seller_id = user.seller_id if hasattr(user, 'seller_id') else user.get('seller_id')
    if not seller_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business profile found")
    table = db.get_table("sellers")
    response = table.get_item(Key={"id": int(seller_id)})
    item = response.get("Item")
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    seller = from_dynamo_item(item)
    for field in ("business_type", "primary_category", "gst_number", "city", "state"):
        seller.setdefault(field, None)
    seller.setdefault("onboarding_completed", False)
    return SimpleNamespace(**seller)


def upsert_seller(db, user, data):
    seller_id = user.seller_id if hasattr(user, 'seller_id') else user.get('seller_id')
    user_id = user.id if hasattr(user, 'id') else user.get('id')
    data_dict = data.model_dump(exclude_unset=True) if hasattr(data, 'model_dump') else data

    sellers_table = db.get_table("sellers")
    users_table = db.get_table("users")
    now = now_iso()

    if seller_id:
        response = sellers_table.get_item(Key={"id": int(seller_id)})
        item = response.get("Item")
        if item:
            item = from_dynamo_item(item)
            item.update(data_dict)
            item["updated_at"] = now
            sellers_table.put_item(Item=to_dynamo_item(item))
            for field in ("business_type", "primary_category", "gst_number", "city", "state"):
                item.setdefault(field, None)
            item.setdefault("onboarding_completed", False)
            return SimpleNamespace(**item)

    # Create new seller
    new_id = db.next_id("sellers")
    seller_item = {
        "id": new_id,
        "business_name": "",
        "business_type": None,
        "primary_category": None,
        "gst_number": None,
        "city": None,
        "state": None,
        "onboarding_completed": False,
        "created_at": now,
        "updated_at": now,
    }
    seller_item.update(data_dict)
    sellers_table.put_item(Item=to_dynamo_item(seller_item))

    # Update user's seller_id
    users_table.update_item(
        Key={"id": int(user_id)},
        UpdateExpression="SET seller_id = :sid, updated_at = :now",
        ExpressionAttributeValues={":sid": new_id, ":now": now},
    )
    # Also update the in-memory user object
    if hasattr(user, 'seller_id'):
        user.seller_id = new_id

    return SimpleNamespace(**seller_item)
