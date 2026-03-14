from datetime import datetime

from fastapi import HTTPException, status

from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.dynamo.helpers import to_dynamo_item, from_dynamo_item, now_iso, query_all
from boto3.dynamodb.conditions import Key


def signup_user(db, email: str, password: str, full_name: str):
    table = db.get_table("users")
    # Check if email already exists using GSI
    response = table.query(
        IndexName="email-index",
        KeyConditionExpression=Key("email").eq(email),
    )
    if response.get("Items"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user_id = db.next_id("users")
    now = now_iso()
    item = to_dynamo_item({
        "id": user_id,
        "email": email,
        "hashed_password": hash_password(password),
        "full_name": full_name,
        "is_email_verified": True,
        "auth_provider": "local",
        "role": "owner",
        "seller_id": None,
        "created_at": now,
        "updated_at": now,
    })
    table.put_item(Item=item)
    return from_dynamo_item(item)


def login_user(db, email: str, password: str) -> dict:
    table = db.get_table("users")
    response = table.query(
        IndexName="email-index",
        KeyConditionExpression=Key("email").eq(email),
    )
    items = response.get("Items", [])
    if not items:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = from_dynamo_item(items[0])
    if not user.get("hashed_password"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return {
        "access_token": create_access_token({"sub": str(user["id"])}),
        "refresh_token": create_refresh_token({"sub": str(user["id"])}),
    }


def refresh_tokens(db, refresh_token: str) -> dict:
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload.get("sub")
    table = db.get_table("users")
    response = table.get_item(Key={"id": int(user_id)})
    if not response.get("Item"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    user = from_dynamo_item(response["Item"])
    return {
        "access_token": create_access_token({"sub": str(user["id"])}),
        "refresh_token": create_refresh_token({"sub": str(user["id"])}),
    }
