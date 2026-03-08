"""Report Spec validation and SQL template compilation.

This is the security boundary between the LLM and the database.
The LLM produces a JSON ReportSpec, which is validated here against
strict rules, then compiled into a safe parameterized SQL query.
"""
import logging
import re as _re
from datetime import date, timedelta
from decimal import Decimal

from pydantic import BaseModel, field_validator
from sqlalchemy import text, bindparam
from sqlalchemy.orm import Session

from app.enums import ReportType
from app.services.sql_templates import TEMPLATES

logger = logging.getLogger(__name__)


class TimeRange(BaseModel):
    type: str = "last_n_days"  # last_n_days | custom
    n: int = 30
    start: str | None = None
    end: str | None = None

    @field_validator("n")
    @classmethod
    def clamp_n(cls, v: int) -> int:
        return max(1, min(v, 365))


ALLOWED_METRICS = {"revenue", "units_sold"}


class ReportSpec(BaseModel):
    report_type: ReportType
    metric: str = "revenue"
    time_range: TimeRange = TimeRange()
    sort: str = "desc"
    limit: int = 10
    horizon_days: int = 7
    threshold: int = 10
    search_query: str | None = None  # For web_search report type

    @field_validator("search_query")
    @classmethod
    def validate_search_query(cls, v: str | None) -> str | None:
        if v is not None:
            return v.strip()[:200]
        return v

    @field_validator("metric")
    @classmethod
    def validate_metric(cls, v: str) -> str:
        if v not in ALLOWED_METRICS:
            return "revenue"
        return v

    @field_validator("limit")
    @classmethod
    def clamp_limit(cls, v: int) -> int:
        return max(1, min(v, 100))

    @field_validator("sort")
    @classmethod
    def validate_sort(cls, v: str) -> str:
        return "DESC" if v.lower() != "asc" else "ASC"

    @field_validator("horizon_days")
    @classmethod
    def validate_horizon(cls, v: int) -> int:
        if v not in (7, 14, 30):
            return 7
        return v

    @field_validator("threshold")
    @classmethod
    def clamp_threshold(cls, v: int) -> int:
        return max(1, min(v, 100))


def _resolve_dates(time_range: TimeRange) -> tuple[date, date]:
    """Resolve a TimeRange into concrete start/end dates."""
    today = date.today()
    if time_range.type == "custom" and time_range.start and time_range.end:
        try:
            start = date.fromisoformat(time_range.start)
            end = date.fromisoformat(time_range.end)
            # Clamp to reasonable range
            if (end - start).days > 365:
                start = end - timedelta(days=365)
            return start, end
        except ValueError:
            pass
    return today - timedelta(days=time_range.n), today


# Mapping from report_type to the table + date column to find latest snapshot
_SNAPSHOT_TABLE_MAP = {
    "inventory_health": ("inventory_snapshots", "snapshot_date"),
    "stockout_risk": ("inventory_snapshots", "snapshot_date"),
    "pricing_analysis": ("price_snapshots", "snapshot_date"),
    "customer_sentiment": ("review_insights", "insight_date"),
    "demand_forecast": ("demand_forecasts", "forecast_date"),
}


def _resolve_snapshot_date(report_type: str, account_ids: tuple, db: Session) -> date:
    """Get the latest available snapshot date for a report type.

    Falls back to today if no snapshot data exists or report doesn't use snapshots.
    """
    mapping = _SNAPSHOT_TABLE_MAP.get(report_type)
    if not mapping:
        return date.today()

    table_name, date_col = mapping
    try:
        stmt = text(
            f"SELECT MAX({date_col}) FROM {table_name} "
            f"WHERE marketplace_account_id IN :account_ids"
        ).bindparams(bindparam("account_ids", expanding=True))
        result = db.execute(stmt, {"account_ids": account_ids}).scalar()
        if result:
            return result
    except Exception as e:
        logger.debug("Snapshot date lookup failed for %s: %s", report_type, e)

    return date.today()


def compile_and_execute(
    spec: ReportSpec,
    account_ids: list[int],
    db: Session,
) -> dict:
    """Compile a validated ReportSpec into SQL and execute it.

    Returns:
        {"columns": [...], "rows": [[...], ...], "report_type": "...", "time_range": "..."}
    """
    report_type = spec.report_type.value
    empty = {"columns": [], "rows": [], "report_type": report_type, "time_range": ""}

    if not account_ids:
        return empty

    if report_type == ReportType.GENERAL.value:
        return {"columns": [], "rows": [], "report_type": report_type, "time_range": ""}

    template_def = TEMPLATES.get(report_type)
    if not template_def:
        logger.warning("Unknown report type: %s", report_type)
        return empty

    start_date, end_date = _resolve_dates(spec.time_range)

    # Resolve snapshot_date to the latest available data instead of today,
    # so queries work even if sync hasn't run today.
    snapshot_date = _resolve_snapshot_date(report_type, tuple(account_ids), db)

    # Build params — always inject account_ids server-side
    params: dict = {
        "account_ids": tuple(account_ids),
        "start_date": start_date,
        "end_date": end_date,
        "limit": spec.limit,
        "snapshot_date": snapshot_date,
        "threshold": spec.threshold,
        "horizon_days": spec.horizon_days,
    }

    # Handle templates with dynamic sort fields (e.g., top_products)
    sql_text = template_def["sql"].text
    if "{sort_field}" in sql_text:
        sort_field = spec.metric if spec.metric in template_def.get("allowed_sort_fields", []) else template_def.get("default_sort_field", "revenue")
        sort_dir = spec.sort
        # Defense-in-depth: ensure sort_field is a bare SQL identifier
        if not _re.match(r"^[a-z_]+$", sort_field):
            sort_field = template_def.get("default_sort_field", "revenue")
        sql_text = sql_text.replace("{sort_field}", sort_field).replace("{sort_dir}", sort_dir)

    stmt = text(sql_text).bindparams(bindparam("account_ids", expanding=True))
    result = db.execute(stmt, params)
    columns = template_def["columns"]
    rows = []
    for row in result:
        row_data = []
        for i, col in enumerate(columns):
            val = row[i]
            if isinstance(val, Decimal):
                val = float(val)
            elif isinstance(val, date):
                val = val.isoformat()
            elif isinstance(val, (list, dict)):
                pass  # JSON columns
            else:
                val = val
            row_data.append(val)
        rows.append(row_data)

    time_desc = f"{start_date.isoformat()} to {end_date.isoformat()}"
    return {
        "columns": columns,
        "rows": rows,
        "report_type": report_type,
        "time_range": time_desc,
    }
