import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.services import amazon_auth_service, marketplace_service

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/amazon", tags=["amazon-auth"])


@router.get("/authorize-url")
def get_authorize_url(
    current_user=Depends(get_current_user),
):
    """Return the Amazon Seller Central OAuth URL for the current user."""
    logger.info("[API /amazon/authorize-url] Called by user_id=%s, email=%s", current_user.id, current_user.email)

    if not current_user.seller_id:
        logger.warning("[API /amazon/authorize-url] User %s has no seller_id — business setup incomplete", current_user.id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Complete business setup first")

    logger.info("[API /amazon/authorize-url] Generating URL for seller_id=%s", current_user.seller_id)
    url = amazon_auth_service.generate_authorize_url(current_user.id, current_user.seller_id)
    logger.info("[API /amazon/authorize-url] Returning authorize URL to client")
    return {"authorize_url": url}


@router.get("/callback")
async def oauth_callback(
    state: str | None = Query(None),
    selling_partner_id: str | None = Query(None),
    spapi_oauth_code: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
    db=Depends(get_db),
):
    """Handle the OAuth redirect from Amazon Seller Central. No auth required — state JWT provides identity."""
    frontend_url = f"{settings.FRONTEND_URL}/dashboard/marketplaces"

    logger.info("=" * 60)
    logger.info("[API /amazon/callback] Amazon OAuth callback received")
    logger.info("[API /amazon/callback] Params: state=%s, selling_partner_id=%s, spapi_oauth_code=%s, error=%s",
                "present" if state else "MISSING",
                selling_partner_id or "MISSING",
                spapi_oauth_code[:10] + "..." if spapi_oauth_code else "MISSING",
                error or "none")

    # Seller denied authorization
    if error:
        logger.warning("[API /amazon/callback] DENIED by seller: error=%s, description=%s", error, error_description)
        params = urlencode({"amazon": "error", "message": error_description or error})
        return RedirectResponse(url=f"{frontend_url}?{params}")

    # Missing required params
    if not state or not selling_partner_id or not spapi_oauth_code:
        missing = [p for p, v in [("state", state), ("selling_partner_id", selling_partner_id), ("spapi_oauth_code", spapi_oauth_code)] if not v]
        logger.error("[API /amazon/callback] Missing required params: %s", missing)
        params = urlencode({"amazon": "error", "message": "Missing required OAuth parameters"})
        return RedirectResponse(url=f"{frontend_url}?{params}")

    try:
        # 1. Verify state token -> extract user_id, seller_id
        logger.info("[API /amazon/callback] Step 1: Verifying state token...")
        token_data = amazon_auth_service.verify_state_token(state)
        logger.info("[API /amazon/callback] State verified: user_id=%s, seller_id=%s", token_data["user_id"], token_data["seller_id"])

        # 2. Exchange auth code for tokens
        logger.info("[API /amazon/callback] Step 2: Exchanging auth code for tokens...")
        tokens = await amazon_auth_service.exchange_auth_code(spapi_oauth_code)
        logger.info("[API /amazon/callback] Token exchange successful")

        # 3. Store refresh token in marketplace account
        logger.info("[API /amazon/callback] Step 3: Saving credentials to DB for seller_id=%s, selling_partner_id=%s",
                    token_data["seller_id"], selling_partner_id)
        account = marketplace_service.connect_amazon_oauth(
            db,
            seller_id=token_data["seller_id"],
            selling_partner_id=selling_partner_id,
            refresh_token=tokens["refresh_token"],
        )
        logger.info("[API /amazon/callback] Marketplace account saved: id=%s, status=%s",
                    account.id if hasattr(account, 'id') else account.get('id'),
                    account.status if hasattr(account, 'status') else account.get('status'))

        logger.info("[API /amazon/callback] SUCCESS — redirecting to frontend")
        logger.info("=" * 60)
        return RedirectResponse(url=f"{frontend_url}?amazon=success")

    except Exception as exc:
        logger.exception("[API /amazon/callback] FAILED — error: %s", exc)
        logger.info("=" * 60)
        params = urlencode({"amazon": "error", "message": str(exc)})
        return RedirectResponse(url=f"{frontend_url}?{params}")
