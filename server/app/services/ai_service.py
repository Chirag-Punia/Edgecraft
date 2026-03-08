"""AI Assistant orchestrator — the core pipeline.

Flow: User message → LLM (Bedrock) → ReportSpec JSON → SQL Template → Execute → LLM Summarize → Response
      OR: User message → LLM → web_search → Tavily → LLM Summarize → Response
"""
import json
import logging
import re
from datetime import datetime, date, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.enums import ChatRole, ReportType
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.marketplace_account import MarketplaceAccount
from app.services.bedrock_client import invoke_bedrock
from app.services.chart_builder import build_chart_data
from app.services.report_spec import ReportSpec, TimeRange, compile_and_execute
from app.services.sql_templates import SCHEMA_CATALOG

logger = logging.getLogger(__name__)
settings = get_settings()

# Maximum chat history turns to include in context
MAX_HISTORY_TURNS = 10

SYSTEM_PROMPT = """You are RetailSutra AI Assistant — an intelligent analytics companion for Indian MSME sellers.
You help sellers understand their business data across Amazon, Flipkart, Shopify, and Facebook Marketplace.

{schema_catalog}

Available report types:
- top_products: Top products by revenue or units sold
- sales_trend: Daily sales/GMV trend
- revenue_summary: Total revenue, orders, units
- order_status: Order count by status
- inventory_health: Current inventory status
- stockout_risk: Products at risk of stocking out
- pricing_analysis: Price comparison (your price vs buybox vs lowest)
- customer_sentiment: Customer review sentiment by product
- demand_forecast: Demand forecast for products
- city_wise_sales: Sales breakdown by city/state
- web_search: When the user asks about market trends, competitor info, industry news, benchmarks, or anything requiring current external information. Include a "search_query" field with the optimized search query.
- general: General conversation (no data query needed)

INSTRUCTIONS:
1. When the user asks a data question, respond with ONLY a valid JSON block wrapped in ```json ... ``` containing a ReportSpec.
2. When the user asks about external info (market trends, news, competitor analysis, industry data), use report_type "web_search" with a "search_query" field.
3. When the user asks a general/greeting/follow-up question, respond conversationally WITHOUT any JSON.
4. The ReportSpec JSON must follow this schema:
   {{
     "report_type": "<one of the types above>",
     "metric": "revenue" | "units_sold",
     "time_range": {{"type": "last_n_days", "n": 30}},
     "sort": "desc" | "asc",
     "limit": 10,
     "threshold": 10,
     "horizon_days": 7,
     "search_query": "optional, only for web_search type"
   }}
5. For inventory/pricing/sentiment/forecast questions, use snapshot_date = today (no time_range needed in spec, system handles it).
6. Detect the user's language automatically. If they write in Hindi, Marathi, Tamil, etc., respond in the SAME language.
7. Be concise, helpful, and business-focused. Use INR (₹) for currency.
8. NEVER output raw SQL. ONLY output the JSON ReportSpec or conversational text.
9. If you're unsure what the user wants, ask a clarifying question.
"""

# ─── Business-advisor summarizer prompt ──────────────────────────────

SUMMARIZE_PROMPT = """You are a sharp retail business advisor for an Indian MSME seller. A chart is shown next to your text — the user already sees the numbers visually. Your job is to add INSIGHT the chart can't show.

{report_instructions}

Context: {report_type} | {time_range} | Language: {language}
{enrichment_context}

Data: {columns}
{data_rows}

FORMAT — follow this EXACTLY:
- Write 2-3 SHORT sentences total. Not paragraphs. Not sub-headings. Just direct text.
- First sentence: the single most important takeaway (with a specific number).
- Second sentence: what action to take RIGHT NOW.
- Optional third sentence: one risk or opportunity to watch.
- Use ₹ with Indian formatting. Bold (**text**) key numbers and product names.
- Do NOT repeat data the chart shows. Do NOT use headers or bullet labels like "Insight:" or "Why:".
- Respond in {language}.

EXAMPLE (for sales_trend):
"**₹1.2L** total GMV this month, but revenue dropped **32%** in the last week — driven by **Brass Diya Set** going out of stock on Mar 3. Restock immediately; you're losing ~₹2,800/day. Weekend sales are consistently 40% lower — try a Saturday flash deal."

EXAMPLE (for top_products):
"**Copper Bottle** alone drives **45%** of your revenue — that's a concentration risk. Diversify by promoting **Jute Bag Set** which has high margins but low visibility. Your bottom 3 products contribute just ₹1,200 combined — consider delisting or bundling them."

Now analyze the data above in this style:
"""

WEB_SEARCH_SUMMARIZE_PROMPT = """You are RetailSutra AI Assistant. The user asked a question that required web search.
Synthesize the search results into a helpful, business-focused response for an Indian MSME seller.

Search query: {search_query}
AI Summary: {ai_answer}

Sources:
{search_context}

Rules:
- Respond in {language}
- Focus on what's actionable for the seller
- Reference sources as [1], [2], etc. when making specific claims
- Be concise: 3-5 key bullet points
- If results are thin, be honest and suggest more specific queries
"""

# ─── Per-report-type advisor instructions ────────────────────────────

REPORT_TYPE_INSTRUCTIONS = {
    "top_products": "Focus: revenue concentration risk if top 1-2 products dominate. Name specific products. Suggest what to promote next.",
    "sales_trend": "Focus: is the trend UP or DOWN this week vs last? Name the best/worst days. Suggest one action (promo, restock, etc.).",
    "revenue_summary": "Focus: AOV vs ₹500-1500 benchmark. What would a 10% AOV improvement mean in ₹/month?",
    "order_status": "Focus: cancellation rate (flag if >5%). Pending/unshipped ratio = fulfillment bottleneck signal.",
    "inventory_health": "Focus: any product at 0 stock = losing sales NOW. Flag unfulfillable items. Name products.",
    "stockout_risk": "Focus: which products stockout in <5 days? Quantify revenue at risk. Give reorder quantity = velocity_7d × 14.",
    "pricing_analysis": "Focus: products losing Buy Box = revenue loss. Name them. Suggest price changes with expected ₹ impact.",
    "customer_sentiment": "Focus: worst-rated product and its #1 fixable complaint. Best-rated product's winning theme.",
    "demand_forecast": "Focus: accelerating vs decelerating products. Which to stock up, which to reduce. Name them.",
    "city_wise_sales": "Focus: top 3 cities' share. Any emerging tier-2 city? Suggest inventory placement.",
}

# ─── Dynamic suggested questions based on report type ────────────────

DYNAMIC_SUGGESTIONS = {
    "top_products": [
        "Which of my top products are at stockout risk?",
        "Show customer sentiment for my top products",
        "What's the pricing analysis for my bestsellers?",
    ],
    "sales_trend": [
        "What's driving the sales change?",
        "Show my top products this month",
        "Which cities are buying the most?",
    ],
    "revenue_summary": [
        "How does this compare to last month?",
        "Show me sales trend for the last 30 days",
        "Which products contribute most to revenue?",
    ],
    "order_status": [
        "Why are so many orders pending?",
        "Show my cancellation trend",
        "What's my fulfillment rate?",
    ],
    "inventory_health": [
        "Which products will stockout soon?",
        "Show demand forecast for low-stock items",
        "What's my dead stock worth?",
    ],
    "stockout_risk": [
        "Show demand forecast for these products",
        "What revenue am I losing from stockouts?",
        "Show my inventory health overview",
    ],
    "pricing_analysis": [
        "Which products am I losing the Buy Box on?",
        "Show my top products by revenue",
        "What's the customer sentiment for repriced products?",
    ],
    "customer_sentiment": [
        "Show details for the most negative product",
        "Which products have improving reviews?",
        "Show my top products by revenue",
    ],
    "demand_forecast": [
        "Show inventory health for high-demand products",
        "Which products are at stockout risk?",
        "Show my sales trend for 30 days",
    ],
    "city_wise_sales": [
        "Show my top products nationally",
        "What's my revenue summary this month?",
        "Show demand forecast for top products",
    ],
    "web_search": [
        "What are the latest Amazon India seller policies?",
        "Show my top products by revenue",
        "What's my sales trend for 30 days?",
    ],
}

DEFAULT_SUGGESTIONS = [
    "What are my top selling products?",
    "Show sales trend for last 30 days",
    "Which products are at stockout risk?",
    "How is my buy box performance?",
    "What are current e-commerce trends in India?",
    "What's my revenue this month?",
]


def _get_account_ids(db: Session, seller_id: int) -> list[int]:
    """Get marketplace account IDs for a seller."""
    return [
        a.id for a in db.query(MarketplaceAccount.id)
        .filter(MarketplaceAccount.seller_id == seller_id)
        .all()
    ]


def _build_messages(history: list[ChatMessage], user_message: str) -> list[dict]:
    """Build Bedrock message array from chat history + new message."""
    messages = []
    for msg in history[-MAX_HISTORY_TURNS:]:
        if msg.role in ("user", "assistant"):
            messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


def _extract_json(text: str) -> dict | None:
    """Extract JSON from a markdown code block or raw JSON in the response."""
    # Try ```json ... ``` block first
    match = re.search(r"```json\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try raw JSON object (supports one level of nested braces for time_range etc.)
    match = re.search(r"\{(?:[^{}]|\{[^{}]*\})*\"report_type\"(?:[^{}]|\{[^{}]*\})*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _generate_title(message: str) -> str:
    """Generate a short title from the first user message."""
    clean = message.strip()[:100]
    if len(clean) > 60:
        clean = clean[:57] + "..."
    return clean


def _build_enrichment_context(
    report_type: str,
    account_ids: list[int],
    db: Session,
) -> str:
    """Pull lightweight cross-data context for the summarizer."""
    context_parts = []

    try:
        if report_type in ("sales_trend", "top_products", "revenue_summary"):
            stockout_spec = ReportSpec(
                report_type=ReportType.STOCKOUT_RISK,
                threshold=10,
                limit=5,
            )
            stockout_data = compile_and_execute(stockout_spec, account_ids, db)
            if stockout_data["rows"]:
                names = [
                    row[2] or row[1]  # product_name or asin
                    for row in stockout_data["rows"][:3]
                ]
                context_parts.append(
                    f"⚠️ Cross-reference: {len(stockout_data['rows'])} products at stockout risk "
                    f"({', '.join(str(n) for n in names)}). Revenue from these could drop if not restocked."
                )

        if report_type in ("stockout_risk", "inventory_health", "demand_forecast"):
            rev_spec = ReportSpec(
                report_type=ReportType.REVENUE_SUMMARY,
                time_range=TimeRange(n=7),
            )
            rev_data = compile_and_execute(rev_spec, account_ids, db)
            if rev_data["rows"] and rev_data["rows"][0][0]:
                rev = rev_data["rows"][0][0]
                context_parts.append(f"📊 Context: Last 7 days total revenue = ₹{rev:,.0f}")

        if report_type in ("pricing_analysis",):
            top_spec = ReportSpec(
                report_type=ReportType.TOP_PRODUCTS,
                limit=3,
                time_range=TimeRange(n=30),
            )
            top_data = compile_and_execute(top_spec, account_ids, db)
            if top_data["rows"]:
                top_names = [str(row[1] or row[0]) for row in top_data["rows"][:3]]
                context_parts.append(
                    f"📊 Top 3 products by revenue (30d): {', '.join(top_names)}. "
                    f"Prioritize Buy Box wins on these."
                )
    except Exception as e:
        logger.debug("Enrichment context error (non-fatal): %s", e)

    return "\n".join(context_parts)


def _handle_web_search(
    spec: ReportSpec,
    message: str,
    lang: str,
) -> tuple[str, list[dict]]:
    """Handle web_search report type. Returns (content, web_sources)."""
    from app.services.web_search import search_web

    search_query = spec.search_query or message
    search_results = search_web(search_query)

    web_sources = [
        {"title": r["title"], "url": r["url"]}
        for r in search_results["results"]
    ]

    if not search_results["results"]:
        return search_results.get("answer", "I couldn't find relevant results. Try rephrasing your question."), web_sources

    search_context = "\n".join(
        f"[{i+1}] {r['title']}: {r['content']}"
        for i, r in enumerate(search_results["results"])
    )

    summarize_system = WEB_SEARCH_SUMMARIZE_PROMPT.format(
        search_query=search_query,
        ai_answer=search_results.get("answer", ""),
        search_context=search_context,
        language=lang,
    )

    try:
        content = invoke_bedrock(
            summarize_system,
            [{"role": "user", "content": message}],
            max_tokens=1024,
            temperature=0.4,
        )
    except Exception:
        # Fallback to Tavily's own answer
        content = search_results.get("answer", "Search completed but summarization failed.")

    return content, web_sources


def get_or_create_session(
    db: Session, session_id: int | None, user_id: int, seller_id: int, language: str = "en"
) -> ChatSession:
    """Get existing session or create a new one."""
    if session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        ).first()
        if session:
            return session

    session = ChatSession(
        seller_id=seller_id,
        user_id=user_id,
        language=language,
    )
    db.add(session)
    db.flush()
    return session


def process_chat(
    db: Session,
    user_id: int,
    seller_id: int,
    message: str,
    session_id: int | None = None,
    language: str | None = None,
) -> dict:
    """Process a chat message through the full AI pipeline."""
    # Sanitize input
    message = message.strip()[:2000]
    if not message:
        return {
            "session_id": session_id,
            "message_id": None,
            "content": "Please enter a message.",
            "report_data": None,
            "chart_data": None,
            "web_sources": [],
            "suggested_questions": DEFAULT_SUGGESTIONS[:3],
            "language": language or "en",
        }

    account_ids = _get_account_ids(db, seller_id)
    lang = language or "en"

    # Get or create session
    session = get_or_create_session(db, session_id, user_id, seller_id, lang)

    # Set title from first message
    if not session.title:
        session.title = _generate_title(message)

    # Save user message
    user_msg = ChatMessage(
        session_id=session.id,
        role=ChatRole.USER,
        content=message,
    )
    db.add(user_msg)
    db.flush()

    # Load chat history
    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    history = [m for m in history if m.id != user_msg.id]

    # Step 1: Call Bedrock to get ReportSpec or conversational response
    system = SYSTEM_PROMPT.format(schema_catalog=SCHEMA_CATALOG)
    bedrock_messages = _build_messages(history, message)

    try:
        llm_response = invoke_bedrock(system, bedrock_messages, temperature=0.1)
    except Exception as e:
        logger.error("Bedrock call failed: %s", e)
        llm_response = None

    if not llm_response:
        content = "I'm having trouble connecting to the AI service right now. Please try again in a moment."
        assistant_msg = ChatMessage(
            session_id=session.id,
            role=ChatRole.ASSISTANT,
            content=content,
        )
        db.add(assistant_msg)
        db.commit()
        return {
            "session_id": session.id,
            "message_id": assistant_msg.id,
            "content": content,
            "report_data": None,
            "chart_data": None,
            "web_sources": [],
            "suggested_questions": DEFAULT_SUGGESTIONS[:3],
            "language": lang,
        }

    # Step 2: Parse ReportSpec or use as conversational response
    spec_json = _extract_json(llm_response)
    report_data = None
    chart_data = None
    web_sources = []
    final_content = llm_response
    resolved_report_type = None

    if spec_json:
        try:
            spec = ReportSpec(**spec_json)
            resolved_report_type = spec.report_type.value

            if spec.report_type == ReportType.WEB_SEARCH:
                # ─── Web Search Branch ───────────────────────
                final_content, web_sources = _handle_web_search(spec, message, lang)

            elif spec.report_type != ReportType.GENERAL:
                # ─── Data Query Branch ───────────────────────
                if not account_ids:
                    final_content = "Please connect a marketplace account first to query your business data."
                else:
                    report_data = compile_and_execute(spec, account_ids, db)

                    if report_data and report_data["rows"]:
                        # Build chart data (deterministic, no LLM)
                        chart_data = build_chart_data(resolved_report_type, report_data)

                        # Replace None product_name with ASIN fallback for LLM context
                        cols = report_data["columns"]
                        pn_idx = cols.index("product_name") if "product_name" in cols else -1
                        asin_idx = cols.index("asin") if "asin" in cols else -1

                        def _clean_row(row):
                            d = dict(zip(cols, row))
                            if pn_idx >= 0 and d.get("product_name") is None and asin_idx >= 0:
                                d["product_name"] = d.get("asin", "Unknown")
                            return d

                        rows_str = "\n".join(
                            str(_clean_row(row))
                            for row in report_data["rows"][:20]
                        )

                        enrichment = _build_enrichment_context(
                            resolved_report_type, account_ids, db
                        )
                        report_instructions = REPORT_TYPE_INSTRUCTIONS.get(
                            resolved_report_type, ""
                        )

                        summarize_system = SUMMARIZE_PROMPT.format(
                            report_type=report_data["report_type"],
                            time_range=report_data["time_range"],
                            language=lang,
                            columns=", ".join(report_data["columns"]),
                            data_rows=rows_str,
                            report_instructions=report_instructions,
                            enrichment_context=enrichment,
                        )

                        summarizer_model = (
                            settings.BEDROCK_SUMMARIZER_MODEL_ID
                            if settings.BEDROCK_SUMMARIZER_MODEL_ID
                            else None
                        )
                        try:
                            final_content = invoke_bedrock(
                                summarize_system,
                                [{"role": "user", "content": "Analyze this data and give actionable business advice."}],
                                max_tokens=1024,
                                temperature=0.4,
                                model_id=summarizer_model,
                            )
                        except Exception:
                            final_content = f"Here are the results for your query ({report_data['report_type']})."
                    else:
                        final_content = "No data found for your query. Make sure you have synced marketplace data."
                        report_data = None
            else:
                # ─── General Conversation ────────────────────
                final_content = re.sub(r"```json\s*\n?.*?\n?\s*```", "", llm_response, flags=re.DOTALL).strip()
                if not final_content:
                    final_content = "How can I help you with your business data?"
        except Exception as e:
            logger.warning("Failed to process ReportSpec: %s", e)
            spec_json = None
            final_content = re.sub(r"```json\s*\n?.*?\n?\s*```", "", llm_response, flags=re.DOTALL).strip()
            if not final_content:
                final_content = llm_response

    # Clean any remaining JSON blocks from conversational responses
    if not report_data and not web_sources:
        final_content = re.sub(r"```json\s*\n?.*?\n?\s*```", "", final_content, flags=re.DOTALL).strip()
        if not final_content:
            final_content = llm_response

    # Dynamic suggested questions based on report type
    suggested = DYNAMIC_SUGGESTIONS.get(
        resolved_report_type, DEFAULT_SUGGESTIONS
    )[:3]

    # Build metadata for persistence
    msg_metadata = {}
    if chart_data:
        msg_metadata["chart_data"] = chart_data
    if web_sources:
        msg_metadata["web_sources"] = web_sources

    # Save assistant message
    assistant_msg = ChatMessage(
        session_id=session.id,
        role=ChatRole.ASSISTANT,
        content=final_content,
        report_spec=spec_json,
        report_data=report_data,
        metadata_=msg_metadata if msg_metadata else None,
    )
    db.add(assistant_msg)
    session.updated_at = datetime.utcnow()
    db.commit()

    return {
        "session_id": session.id,
        "message_id": assistant_msg.id,
        "content": final_content,
        "report_data": report_data,
        "chart_data": chart_data,
        "web_sources": web_sources,
        "suggested_questions": suggested,
        "language": session.language or lang,
    }
