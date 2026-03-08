"""Customer review sentiment analysis service.

Analyzes reviews using AWS Bedrock to extract sentiment, topics, and insights.
Falls back to rule-based analysis if Bedrock is unavailable.
"""
import json
import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.models.customer_review import CustomerReview
from app.models.review_insight import ReviewInsight
from app.services.bedrock_client import invoke_bedrock
from app.services.report_generator import _extract_json

logger = logging.getLogger(__name__)

SENTIMENT_PROMPT = """Analyze these customer reviews for a product sold on Amazon India.
Return a JSON object with:
{{
  "avg_sentiment": <float from -1.0 (very negative) to 1.0 (very positive)>,
  "positive_count": <int>,
  "negative_count": <int>,
  "neutral_count": <int>,
  "top_topics": [<top 3-5 discussion topics>],
  "top_complaints": [<top 3 complaints>],
  "top_praises": [<top 3 positive things>],
  "summary": "<2-3 sentence summary of overall sentiment>"
}}

Reviews:
{reviews_text}

Return ONLY valid JSON, no other text."""

CATEGORY_TOPICS = {
    "Kitchen": {
        "topics": ["build quality", "heat retention", "non-stick coating", "handle grip", "ease of cleaning"],
        "complaints": ["non-stick coating peeling", "poor heat retention", "loose handle"],
        "praises": ["solid build quality", "great heat retention", "easy to wash"],
    },
    "Appliances": {
        "topics": ["build quality", "performance", "noise level", "energy efficiency", "heating speed"],
        "complaints": ["stopped working early", "noisy operation", "overheating"],
        "praises": ["fast performance", "energy efficient", "quiet operation"],
    },
    "Electronics": {
        "topics": ["battery life", "connectivity", "sound quality", "charging speed", "build quality"],
        "complaints": ["battery drains fast", "connectivity drops", "poor sound quality"],
        "praises": ["long battery life", "seamless connectivity", "excellent sound quality"],
    },
    "Home": {
        "topics": ["fabric quality", "color accuracy", "stitching", "shrinkage", "comfort"],
        "complaints": ["color fading", "shrinkage after wash", "poor stitching"],
        "praises": ["beautiful color", "soft fabric", "neat stitching"],
    },
    "Personal Care": {
        "topics": ["fragrance", "skin feel", "packaging quality", "ingredients", "lasting effect"],
        "complaints": ["skin irritation", "chemical fragrance", "damaged packaging"],
        "praises": ["pleasant fragrance", "smooth skin feel", "premium packaging"],
    },
    "Bags": {
        "topics": ["zipper quality", "waterproofing", "compartments", "strap comfort", "durability"],
        "complaints": ["zipper broke", "not waterproof", "uncomfortable straps"],
        "praises": ["smooth zipper", "waterproof design", "comfortable straps"],
    },
}

DEFAULT_TOPICS = {
    "topics": ["quality", "delivery", "value for money"],
    "complaints": ["product quality", "packaging", "late delivery"],
    "praises": ["good quality", "fast delivery", "value for money"],
}


def _get_category_topics(category: str | None) -> dict:
    """Get category-specific topics for rule-based analysis."""
    if not category:
        return DEFAULT_TOPICS
    for key, val in CATEGORY_TOPICS.items():
        if key.lower() in category.lower() or category.lower() in key.lower():
            return val
    return DEFAULT_TOPICS


def _resolve_category(asin: str) -> str | None:
    """Look up category from the PRODUCTS catalog by ASIN."""
    try:
        from app.services.mock_amazon_data import PRODUCTS
        for p in PRODUCTS:
            if p["asin"] == asin:
                return p["category"]
    except Exception:
        pass
    return None


def _rule_based_analysis(reviews: list[CustomerReview], category: str | None = None) -> dict:
    """Fallback rule-based sentiment when Bedrock is unavailable."""
    positive = sum(1 for r in reviews if r.rating >= 4)
    negative = sum(1 for r in reviews if r.rating <= 2)
    neutral = len(reviews) - positive - negative

    avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else 3
    avg_sentiment = round((avg_rating - 3) / 2, 2)

    cat_topics = _get_category_topics(category)

    neg_ratio = negative / max(len(reviews), 1)
    if neg_ratio > 0.4:
        topics = cat_topics["complaints"][:2] + cat_topics["topics"][:1]
        complaints = cat_topics["complaints"]
        praises = cat_topics["praises"][:1]
    elif neg_ratio > 0.2:
        topics = cat_topics["topics"][:3]
        complaints = cat_topics["complaints"][:2] + ["inconsistent quality"]
        praises = cat_topics["praises"][:2]
    else:
        topics = cat_topics["topics"][:3]
        complaints = cat_topics["complaints"][:1] + ["minor packaging issues"]
        praises = cat_topics["praises"]

    return {
        "avg_sentiment": avg_sentiment,
        "positive_count": positive,
        "negative_count": negative,
        "neutral_count": neutral,
        "top_topics": topics,
        "top_complaints": complaints,
        "top_praises": praises,
        "summary": f"Based on {len(reviews)} reviews, average rating is {avg_rating:.1f}/5. "
                   f"{positive} positive, {negative} negative, {neutral} neutral.",
    }


def analyze_reviews_for_product(
    db: Session,
    marketplace_account_id: int,
    asin: str,
) -> dict:
    """Analyze all reviews for a specific product."""
    reviews = (
        db.query(CustomerReview)
        .filter(
            CustomerReview.marketplace_account_id == marketplace_account_id,
            CustomerReview.asin == asin,
        )
        .order_by(CustomerReview.review_date.desc())
        .limit(50)
        .all()
    )

    if not reviews:
        return None

    category = _resolve_category(asin)

    # Try Bedrock first
    try:
        reviews_text = "\n".join(
            f"Rating: {r.rating}/5 | Title: {r.title} | Body: {r.body}"
            for r in reviews[:30]
        )
        prompt = SENTIMENT_PROMPT.format(reviews_text=reviews_text)
        response = invoke_bedrock(
            "You are a sentiment analysis expert. Return only valid JSON.",
            [{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.1,
        )
        result = _extract_json(response)
        if not result:
            raise ValueError(f"Could not parse JSON from LLM response: {response[:200]}")
        return result
    except Exception as e:
        logger.warning("Bedrock sentiment analysis failed, using rule-based: %s", e)
        return _rule_based_analysis(reviews, category)


def compute_all_insights(db: Session, marketplace_account_id: int):
    """Compute sentiment insights for all products with reviews."""
    asins = (
        db.query(CustomerReview.asin)
        .filter(CustomerReview.marketplace_account_id == marketplace_account_id)
        .distinct()
        .all()
    )

    today = date.today()
    count = 0

    for (asin,) in asins:
        if not asin:
            continue

        analysis = analyze_reviews_for_product(db, marketplace_account_id, asin)
        if not analysis:
            continue

        values = {
            "marketplace_account_id": marketplace_account_id,
            "asin": asin,
            "insight_date": today,
            "avg_sentiment": max(Decimal("-1"), min(Decimal("1"), Decimal(str(analysis.get("avg_sentiment", 0))))),
            "positive_count": analysis.get("positive_count", 0),
            "negative_count": analysis.get("negative_count", 0),
            "neutral_count": analysis.get("neutral_count", 0),
            "top_topics": analysis.get("top_topics"),
            "top_complaints": analysis.get("top_complaints"),
            "top_praises": analysis.get("top_praises"),
            "summary": analysis.get("summary"),
        }

        stmt = mysql_insert(ReviewInsight).values(**values)
        stmt = stmt.on_duplicate_key_update(
            avg_sentiment=stmt.inserted.avg_sentiment,
            positive_count=stmt.inserted.positive_count,
            negative_count=stmt.inserted.negative_count,
            neutral_count=stmt.inserted.neutral_count,
            top_topics=stmt.inserted.top_topics,
            top_complaints=stmt.inserted.top_complaints,
            top_praises=stmt.inserted.top_praises,
            summary=stmt.inserted.summary,
        )
        db.execute(stmt)
        count += 1

    db.commit()
    logger.info("Computed sentiment insights for %d products (account=%d)", count, marketplace_account_id)
    return count
