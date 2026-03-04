import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from jose import jwt, JWTError

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

AMAZON_AUTH_BASE = "https://sellercentral.amazon.in/apps/authorize/consent"
AMAZON_TOKEN_URL = "https://api.amazon.com/auth/o2/token"


def generate_authorize_url(user_id: int, seller_id: int) -> str:
    """Build the Amazon Seller Central OAuth authorization URL with a signed state token."""
    logger.info("[OAuth] Generating authorize URL for user_id=%s, seller_id=%s", user_id, seller_id)

    state_payload = {
        "user_id": user_id,
        "seller_id": seller_id,
        "type": "amazon_oauth",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    state = jwt.encode(state_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    logger.debug("[OAuth] State JWT created (expires in 10min)")

    params = {
        "application_id": settings.SP_API_APP_ID,
        "state": state,
        "redirect_uri": settings.SP_API_REDIRECT_URI,
        "version": "beta",  # Required for draft/unpublished apps
    }
    url = f"{AMAZON_AUTH_BASE}?{urlencode(params)}"
    logger.info("[OAuth] Authorize URL generated: app_id=%s, redirect_uri=%s", settings.SP_API_APP_ID, settings.SP_API_REDIRECT_URI)
    logger.debug("[OAuth] Full URL: %s", url)
    return url


def verify_state_token(state: str) -> dict:
    """Decode and verify the OAuth state JWT. Returns {user_id, seller_id}."""
    logger.info("[OAuth] Verifying state token (length=%d)", len(state))
    try:
        payload = jwt.decode(state, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as e:
        logger.error("[OAuth] State token verification FAILED: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state token")

    if payload.get("type") != "amazon_oauth":
        logger.error("[OAuth] State token has wrong type: %s", payload.get("type"))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state token type")

    result = {"user_id": payload["user_id"], "seller_id": payload["seller_id"]}
    logger.info("[OAuth] State token verified: user_id=%s, seller_id=%s", result["user_id"], result["seller_id"])
    return result


async def exchange_auth_code(spapi_oauth_code: str) -> dict:
    """Exchange the SP-API OAuth code for refresh + access tokens via Amazon's LWA endpoint."""
    logger.info("[OAuth] Exchanging auth code with Amazon LWA (code=%s...)", spapi_oauth_code[:10])
    logger.debug("[OAuth] Token endpoint: %s", AMAZON_TOKEN_URL)
    logger.debug("[OAuth] Using client_id=%s, redirect_uri=%s", settings.SP_API_LWA_APP_ID, settings.SP_API_REDIRECT_URI)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            AMAZON_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": spapi_oauth_code,
                "client_id": settings.SP_API_LWA_APP_ID,
                "client_secret": settings.SP_API_LWA_CLIENT_SECRET,
                "redirect_uri": settings.SP_API_REDIRECT_URI,
            },
        )

    logger.info("[OAuth] Amazon LWA response: status=%d", resp.status_code)

    if resp.status_code != 200:
        logger.error("[OAuth] Token exchange FAILED: status=%d, body=%s", resp.status_code, resp.text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Amazon token exchange failed: {resp.text}",
        )

    data = resp.json()
    logger.info("[OAuth] Token exchange SUCCESS: got refresh_token (length=%d), access_token expires_in=%s",
                len(data.get("refresh_token", "")), data.get("expires_in"))
    return {
        "refresh_token": data["refresh_token"],
        "access_token": data["access_token"],
        "expires_in": data["expires_in"],
    }
