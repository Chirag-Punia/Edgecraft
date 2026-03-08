"""AI Report Generator — collects data, prompts the LLM, caches results."""
import json
import logging
import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.ai_report import AIReport
from app.models.marketplace_account import MarketplaceAccount
from app.services.bedrock_client import invoke_bedrock
from app.services.report_data_collector import COLLECTORS

logger = logging.getLogger(__name__)

REPORT_CONFIGS = {
    "business_health": {
        "title": "Business Health Scorecard",
        "description": "AI-scored health across sales, inventory, pricing, sentiment, and demand.",
        "prompt": """You are a retail analytics expert scoring a small Indian MSME seller's business health.

DATA:
{data}

TASK:
1. Score each dimension 0-100: Sales Momentum, Inventory Health, Pricing Competitiveness, Customer Satisfaction, Demand Outlook.
   - Sales: based on revenue trend and cancel rate
   - Inventory: based on low stock % and stockout risk
   - Pricing: based on buy box win rate
   - Satisfaction: based on avg sentiment (-1 to 1 scale, map to 0-100)
   - Demand: based on stockout risk count
2. Compute overall score = weighted average (Sales 30%, Inventory 25%, Pricing 20%, Satisfaction 15%, Demand 10%).
3. Identify the single biggest risk and one quick-win action.

OUTPUT FORMAT (follow EXACTLY):
```json
{{"overall_score": <int>, "dimensions": {{"sales": <int>, "inventory": <int>, "pricing": <int>, "satisfaction": <int>, "demand": <int>}}, "biggest_risk": "<one word category>", "quick_win": "<one sentence action>"}}
```

Then write a 3-4 sentence narrative summary explaining the score, the biggest risk, and what to do first. Be specific with numbers. Use ₹ for currency.""",
    },

    "product_matrix": {
        "title": "Product Risk & Opportunity Matrix",
        "description": "AI classifies each product as Star, Cash Cow at Risk, Hidden Gem, or Problem Child.",
        "prompt": """You are a product portfolio strategist for an Indian MSME Amazon seller.

DATA (per product — revenue, stock, buy box, sentiment, stockout risk):
{data}

TASK:
Classify each product into one of 4 quadrants:
- **Star**: High revenue + good signals (winning buy box, positive sentiment, healthy stock)
- **Cash Cow at Risk**: High revenue BUT deteriorating signals (losing buy box, negative reviews, low stock)
- **Hidden Gem**: Lower revenue but improving/good signals — potential to grow
- **Problem Child**: Issues across the board (low revenue, bad reviews, pricing problems)

For each product write ONE action sentence.

OUTPUT FORMAT:
```json
{{"products": [{{"name": "...", "quadrant": "star|cash_cow_at_risk|hidden_gem|problem_child", "action": "..."}}]}}
```

Then write a 2-3 sentence portfolio summary: how many stars vs problems, the #1 action to take. Be specific with product names and numbers.""",
    },

    "revenue_leakage": {
        "title": "Revenue Leakage Analysis",
        "description": "AI estimates revenue lost from cancellations, pricing gaps, and stockouts.",
        "prompt": """You are a revenue recovery analyst for an Indian MSME Amazon seller.

DATA:
{data}

TASK:
Estimate total revenue being leaked from 3 sources:
1. **Cancellations**: Direct lost revenue from cancelled orders
2. **Pricing Gaps**: Products losing buy box — estimate lost sales (assume 30% of current revenue lost when not winning buy box)
3. **Stockout Risk**: Products about to stock out — estimate weekly revenue at risk based on predicted demand

Prioritize which leak to fix first based on recoverable amount.
Look for connections — e.g. if a product losing buy box also has negative reviews, that's a deeper issue.

OUTPUT FORMAT:
```json
{{"leakage_summary": {{"cancellations": <float>, "pricing_gaps": <float>, "stockout_risk": <float>, "total": <float>}}, "priority": "<which to fix first>", "connections": ["<insight about linked issues>"]}}
```

Then write 3-4 sentences: total leakage amount, what to fix first and why, any connected issues you spotted. Use ₹ for all amounts.""",
    },

    "weekly_digest": {
        "title": "Weekly Business Digest",
        "description": "AI-written executive summary of your week — wins, risks, and next steps.",
        "prompt": """You are a business advisor writing a weekly briefing for an Indian MSME seller.

THIS WEEK'S DATA:
{data}

TASK:
Write a concise weekly digest covering:
1. **Performance**: Revenue and order trends vs last week
2. **Wins**: What went well (top products, improvements)
3. **Risks**: What needs attention (stockouts, pricing, sentiment)
4. **Action Plan**: Top 3 things to do this week, ordered by impact

OUTPUT FORMAT:
```json
{{"headline": "<one-line summary of the week>", "action_items": ["<action 1>", "<action 2>", "<action 3>"]}}
```

Then write 4-5 sentences as a narrative digest. Be specific — use product names, ₹ amounts, and percentages. Write as if talking to the seller directly.""",
    },

    "pricing_strategy": {
        "title": "Pricing Strategy Recommendations",
        "description": "AI analyzes each product's pricing position with quality-aware repricing advice.",
        "prompt": """You are a pricing strategist for an Indian MSME Amazon seller.

DATA (per product — your price, buy box price, lowest, sentiment score, revenue):
{data}

TASK:
For each product, recommend a pricing action considering:
- Price gap to buy box (can you match?)
- Sentiment score (high sentiment = quality advantage, justify premium; low = must compete on price)
- Revenue contribution (high-revenue products = higher priority)

Don't blindly recommend "lower to match buy box." If a product has great reviews (sentiment > 0.3), a small premium is justified.

OUTPUT FORMAT:
```json
{{"recommendations": [{{"name": "...", "action": "reduce|hold|increase", "target_price": <float>, "reasoning": "..."}}]}}
```

Then write 2-3 sentences summarizing the overall pricing strategy: how many to reduce, how many can hold premium, estimated revenue impact.""",
    },
}

CACHE_HOURS = 6


def _get_account_ids(db: Session, seller_id: int) -> list[int]:
    return [
        a.id for a in db.query(MarketplaceAccount.id)
        .filter(MarketplaceAccount.seller_id == seller_id).all()
    ]


def _extract_json(text: str) -> dict | None:
    """Extract JSON block from LLM response."""
    # Try fenced JSON block (```json ... ``` or ``` ... ```)
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try finding outermost JSON object
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def generate_report(
    db: Session,
    seller_id: int,
    report_type: str,
    force: bool = False,
) -> AIReport:
    """Generate or return cached AI report."""
    config = REPORT_CONFIGS.get(report_type)
    if not config:
        raise ValueError(f"Unknown report type: {report_type}")

    # Check cache
    if not force:
        cached = (
            db.query(AIReport)
            .filter(AIReport.seller_id == seller_id, AIReport.report_type == report_type,
                    AIReport.status == "ready", AIReport.expires_at > datetime.utcnow())
            .first()
        )
        if cached:
            return cached

    # Check if already generating (with 5-min stuck timeout)
    generating = (
        db.query(AIReport)
        .filter(AIReport.seller_id == seller_id, AIReport.report_type == report_type,
                AIReport.status == "generating")
        .first()
    )
    if generating:
        stuck_threshold = datetime.utcnow() - timedelta(minutes=5)
        if generating.generated_at and generating.generated_at > stuck_threshold:
            return generating
        # Stuck — reset and regenerate

    # Upsert: create or update record
    report = (
        db.query(AIReport)
        .filter(AIReport.seller_id == seller_id, AIReport.report_type == report_type)
        .first()
    )
    if not report:
        report = AIReport(seller_id=seller_id, report_type=report_type)
        db.add(report)

    report.status = "generating"
    report.generated_at = datetime.utcnow()
    try:
        db.commit()
    except Exception:
        db.rollback()
        # Another request won the race — return whatever exists
        existing = db.query(AIReport).filter(
            AIReport.seller_id == seller_id, AIReport.report_type == report_type).first()
        if existing:
            return existing
        raise
    db.refresh(report)

    try:
        account_ids = _get_account_ids(db, seller_id)
        if not account_ids:
            report.status = "ready"
            report.ai_narrative = "No marketplace connected yet. Connect a marketplace and sync data to generate this report."
            report.report_data = {}
            report.generated_at = datetime.utcnow()
            report.expires_at = datetime.utcnow() + timedelta(hours=CACHE_HOURS)
            db.commit()
            return report

        # Collect data
        collector = COLLECTORS[report_type]
        data = collector(db, account_ids)

        # Build prompt — data goes in user message to prevent injection
        data_str = json.dumps(data, indent=2, default=str)
        system_prompt = config["prompt"].replace("{data}", "See the DATA section in the user message.")

        llm_response = invoke_bedrock(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": f"DATA:\n{data_str}\n\nGenerate the report now."}],
            max_tokens=1500,
            temperature=0.3,
        )

        # Parse structured data from response
        parsed_json = _extract_json(llm_response)

        # Extract narrative (text outside the JSON block)
        narrative = ""
        json_match = re.search(r"```(?:json)?\s*\n?.*?```", llm_response, re.DOTALL)
        if json_match:
            before = llm_response[:json_match.start()].strip()
            after = llm_response[json_match.end():].strip()
            narrative = f"{before}\n\n{after}".strip() if before and after else (after or before)
        if not narrative:
            # Strip any JSON-like blocks and use remaining text
            cleaned = re.sub(r"```(?:json)?\s*\n?.*?```", "", llm_response, flags=re.DOTALL).strip()
            # Also strip bare JSON objects
            cleaned = re.sub(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", "", cleaned, flags=re.DOTALL).strip()
            narrative = cleaned if cleaned else "Report generated successfully. Review the structured data for details."

        # Extract score for health scorecard
        score = None
        if report_type == "business_health" and parsed_json:
            score = parsed_json.get("overall_score")

        report.status = "ready"
        report.ai_narrative = narrative
        report.report_data = parsed_json or data
        report.score = score
        report.generated_at = datetime.utcnow()
        report.expires_at = datetime.utcnow() + timedelta(hours=CACHE_HOURS)
        db.commit()

    except Exception as e:
        logger.error("Report generation failed for %s/%s: %s", seller_id, report_type, e)
        report.status = "failed"
        report.ai_narrative = "Report generation failed. Please try again."
        report.generated_at = datetime.utcnow()
        report.expires_at = datetime.utcnow() + timedelta(minutes=5)
        db.commit()

    return report
