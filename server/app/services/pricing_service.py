"""Pricing recommendation service.

Analyzes price snapshots to generate pricing recommendations:
- Compare your price vs buy box vs lowest competitor
- Compute recommended price bands
- Determine price action (reduce/hold/increase)
"""
import logging
from datetime import date
from decimal import Decimal

from boto3.dynamodb.conditions import Key

from app.dynamo.helpers import to_dynamo_item, query_all, now_iso, batch_write_items

logger = logging.getLogger(__name__)


def compute_recommendations(db, marketplace_account_id: int):
    """Compute pricing recommendations for all products."""
    today = date.today()
    today_iso = today.isoformat()

    price_table = db.get_table("price_snapshots")
    rec_table = db.get_table("pricing_recommendations")

    # Query all price snapshots for this account and filter for today
    all_snapshots = query_all(
        price_table,
        KeyConditionExpression=Key("marketplace_account_id").eq(marketplace_account_id),
    )
    snapshots = [s for s in all_snapshots if s.get("snapshot_date") == today_iso]

    rec_batch = []
    for snap in snapshots:
        your_price = float(snap.get("your_price") or 0)
        buybox = float(snap.get("buybox_price") or 0)
        lowest = float(snap.get("lowest_price") or 0)

        if your_price <= 0:
            continue

        is_buybox_winner = snap.get("is_buybox_winner", False)

        # Determine action and recommended price
        if is_buybox_winner:
            action = "hold"
            recommended = your_price
            reasoning = f"You are winning the buy box at INR {your_price:.0f}. Hold your current price."
        elif buybox > 0 and your_price > buybox:
            gap_pct = ((your_price - buybox) / buybox) * 100
            if gap_pct > 10:
                action = "reduce"
                recommended = round(buybox * 0.99, 2)  # Slightly undercut buybox
                reasoning = (
                    f"Your price (INR {your_price:.0f}) is {gap_pct:.1f}% above buy box "
                    f"(INR {buybox:.0f}). Reduce to INR {recommended:.0f} to win buy box."
                )
            else:
                action = "reduce"
                recommended = round(buybox, 2)
                reasoning = (
                    f"Your price (INR {your_price:.0f}) is slightly above buy box "
                    f"(INR {buybox:.0f}). Match buy box price to compete."
                )
        elif buybox > 0 and your_price < buybox * 0.85:
            action = "increase"
            recommended = round(buybox * 0.95, 2)
            reasoning = (
                f"Your price (INR {your_price:.0f}) is well below buy box "
                f"(INR {buybox:.0f}). You could increase to INR {recommended:.0f} "
                f"and still win while improving margins."
            )
        else:
            action = "hold"
            recommended = your_price
            reasoning = f"Your price (INR {your_price:.0f}) is competitive. Hold current position."

        margin_impact = ((recommended - your_price) / your_price * 100) if your_price > 0 else 0

        asin = snap.get("asin")
        asin_date = f"{asin}#{today_iso}"
        now = now_iso()

        item = {
            "marketplace_account_id": marketplace_account_id,
            "asin_date": asin_date,
            "asin": asin,
            "seller_sku": snap.get("seller_sku"),
            "recommendation_date": today_iso,
            "current_price": Decimal(str(your_price)),
            "buybox_price": Decimal(str(buybox)) if buybox else None,
            "lowest_competitor": Decimal(str(lowest)) if lowest else None,
            "recommended_price": Decimal(str(round(recommended, 2))),
            "price_action": action,
            "margin_impact_pct": Decimal(str(round(margin_impact, 2))),
            "reasoning": reasoning,
            "created_at": now,
            "updated_at": now,
        }

        rec_batch.append(to_dynamo_item(item))

    if rec_batch:
        batch_write_items(rec_table, rec_batch)

    logger.info("Computed %d pricing recommendations (account=%d)", len(rec_batch), marketplace_account_id)
    return len(rec_batch)
