"""Pricing recommendation service.

Analyzes price snapshots to generate pricing recommendations:
- Compare your price vs buy box vs lowest competitor
- Compute recommended price bands
- Determine price action (reduce/hold/increase)
"""
import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.models.price_snapshot import PriceSnapshot
from app.models.pricing_recommendation import PricingRecommendation

logger = logging.getLogger(__name__)


def compute_recommendations(db: Session, marketplace_account_id: int):
    """Compute pricing recommendations for all products."""
    today = date.today()

    snapshots = (
        db.query(PriceSnapshot)
        .filter(
            PriceSnapshot.marketplace_account_id == marketplace_account_id,
            PriceSnapshot.snapshot_date == today,
        )
        .all()
    )

    count = 0
    for snap in snapshots:
        your_price = float(snap.your_price or 0)
        buybox = float(snap.buybox_price or 0)
        lowest = float(snap.lowest_price or 0)

        if your_price <= 0:
            continue

        # Determine action and recommended price
        if snap.is_buybox_winner:
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

        values = {
            "marketplace_account_id": marketplace_account_id,
            "asin": snap.asin,
            "seller_sku": snap.seller_sku,
            "recommendation_date": today,
            "current_price": snap.your_price,
            "buybox_price": snap.buybox_price,
            "lowest_competitor": snap.lowest_price,
            "recommended_price": Decimal(str(round(recommended, 2))),
            "price_action": action,
            "margin_impact_pct": Decimal(str(round(margin_impact, 2))),
            "reasoning": reasoning,
        }

        stmt = mysql_insert(PricingRecommendation).values(**values)
        stmt = stmt.on_duplicate_key_update(
            current_price=stmt.inserted.current_price,
            buybox_price=stmt.inserted.buybox_price,
            lowest_competitor=stmt.inserted.lowest_competitor,
            recommended_price=stmt.inserted.recommended_price,
            price_action=stmt.inserted.price_action,
            margin_impact_pct=stmt.inserted.margin_impact_pct,
            reasoning=stmt.inserted.reasoning,
        )
        db.execute(stmt)
        count += 1

    db.commit()
    logger.info("Computed %d pricing recommendations (account=%d)", count, marketplace_account_id)
    return count
