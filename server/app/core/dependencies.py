from types import SimpleNamespace
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.db.session import get_db
from app.core.security import decode_token
from app.dynamo.helpers import from_dynamo_item

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db=Depends(get_db),
):
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    table = db.get_table("users")
    response = table.get_item(Key={"id": int(user_id)})
    item = response.get("Item")
    if item is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    user = from_dynamo_item(item)
    # Ensure optional fields have defaults (DynamoDB omits None values)
    user.setdefault("seller_id", None)
    user.setdefault("is_email_verified", False)
    user.setdefault("auth_provider", "local")
    user.setdefault("role", "owner")
    return SimpleNamespace(**user)
