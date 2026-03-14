"""Customer review sentiment analysis service.

Analyzes reviews using AWS Bedrock to extract sentiment, topics, and insights.
Falls back to rule-based analysis if Bedrock is unavailable.
"""
import json
import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from boto3.dynamodb.conditions import Key

from app.dynamo.helpers import to_dynamo_item, query_all, now_iso, batch_write_items
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


def _rule_based_analysis(reviews: list, category: str | None = None) -> dict:
    """Fallback rule-based sentiment when Bedrock is unavailable.

    Accepts reviews as list of dicts or SimpleNamespace objects.
    """
    def _rating(r):
        return r.rating if hasattr(r, "rating") else r.get("rating", 3)

    positive = sum(1 for r in reviews if _rating(r) >= 4)
    negative = sum(1 for r in reviews if _rating(r) <= 2)
    neutral = len(reviews) - positive - negative

    avg_rating = sum(_rating(r) for r in reviews) / len(reviews) if reviews else 3
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
    db,
    marketplace_account_id: int,
    asin: str,
) -> dict:
    """Analyze all reviews for a specific product."""
    review_table = db.get_table("customer_reviews")

    # Query reviews by PK (marketplace_account_id) and filter by asin
    from boto3.dynamodb.conditions import Attr
    all_reviews = query_all(
        review_table,
        KeyConditionExpression=Key("marketplace_account_id").eq(marketplace_account_id),
        FilterExpression=Attr("asin").eq(asin),
    )

    if not all_reviews:
        return None

    # Sort by review_date descending, limit to 50
    all_reviews.sort(key=lambda r: r.get("review_date", ""), reverse=True)
    reviews = all_reviews[:50]

    # Convert to SimpleNamespace for attribute access
    review_objs = [SimpleNamespace(**r) for r in reviews]

    category = _resolve_category(asin)

    # Try Bedrock first
    try:
        reviews_text = "\n".join(
            f"Rating: {r.rating}/5 | Title: {r.title} | Body: {r.body}"
            for r in review_objs[:30]
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
        return _rule_based_analysis(review_objs, category)


def _analyze_reviews_direct(reviews: list, asin: str) -> dict:
    """Analyze pre-fetched reviews for a product (no DB call)."""
    if not reviews:
        return None

    # Sort by review_date descending, limit to 50
    reviews = sorted(reviews, key=lambda r: r.get("review_date", ""), reverse=True)[:50]

    review_objs = [SimpleNamespace(**r) for r in reviews]
    category = _resolve_category(asin)

    # Try Bedrock first
    try:
        reviews_text = "\n".join(
            f"Rating: {r.rating}/5 | Title: {r.title} | Body: {r.body}"
            for r in review_objs[:30]
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
        return _rule_based_analysis(review_objs, category)


def compute_all_insights(db, marketplace_account_id: int):
    """Compute sentiment insights for all products with reviews."""
    review_table = db.get_table("customer_reviews")
    insight_table = db.get_table("review_insights")

    # Get all reviews for this account
    all_reviews = query_all(
        review_table,
        KeyConditionExpression=Key("marketplace_account_id").eq(marketplace_account_id),
    )

    # Group reviews by ASIN in Python (fixes N+1 query bug)
    reviews_by_asin = defaultdict(list)
    for r in all_reviews:
        asin = r.get("asin")
        if asin:
            reviews_by_asin[asin].append(r)

    today = date.today()
    today_iso = today.isoformat()
    insight_batch = []

    for asin, asin_reviews in reviews_by_asin.items():
        analysis = _analyze_reviews_direct(asin_reviews, asin)
        if not analysis:
            continue

        asin_date = f"{asin}#{today_iso}"
        now = now_iso()

        top_topics = analysis.get("top_topics")
        top_complaints = analysis.get("top_complaints")
        top_praises = analysis.get("top_praises")

        item = {
            "marketplace_account_id": marketplace_account_id,
            "asin_date": asin_date,
            "asin": asin,
            "insight_date": today_iso,
            "avg_sentiment": Decimal(str(max(-1, min(1, analysis.get("avg_sentiment", 0))))),
            "positive_count": analysis.get("positive_count", 0),
            "negative_count": analysis.get("negative_count", 0),
            "neutral_count": analysis.get("neutral_count", 0),
            "top_topics": top_topics,
            "top_complaints": top_complaints,
            "top_praises": top_praises,
            "summary": analysis.get("summary"),
            "created_at": now,
            "updated_at": now,
        }

        insight_batch.append(to_dynamo_item(item))

    if insight_batch:
        batch_write_items(insight_table, insight_batch)

    logger.info("Computed sentiment insights for %d products (account=%d)", len(insight_batch), marketplace_account_id)
    return len(insight_batch)
