"""Report Spec validation and DynamoDB query execution.

This is the security boundary between the LLM and the database.
The LLM produces a JSON ReportSpec, which is validated here against
strict rules, then dispatched to the appropriate DynamoDB query function.
"""
import logging
import re as _re
from datetime import date, timedelta

from pydantic import BaseModel, field_validator

from app.enums import ReportType
from app.services.sql_templates import TEMPLATES
from app.dynamo.helpers import query_by_account_ids

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


# Mapping from report_type to the table + sort-key field to find latest snapshot
_SNAPSHOT_TABLE_MAP = {
    "inventory_health": ("inventory_snapshots", "sku_date"),
    "stockout_risk": ("inventory_snapshots", "sku_date"),
    "pricing_analysis": ("price_snapshots", "asin_date"),
    "customer_sentiment": ("review_insights", "asin_date"),
    "demand_forecast": ("demand_forecasts", "asin_date_horizon"),
}


def _resolve_snapshot_date(report_type: str, account_ids: list[int], db) -> date:
    """Get the latest available snapshot date for a report type.

    Falls back to today if no snapshot data exists or report doesn't use snapshots.
    Queries DynamoDB partitions and extracts dates from sort keys.
    """
    mapping = _SNAPSHOT_TABLE_MAP.get(report_type)
    if not mapping:
        return date.today()

    table_name, sk_field = mapping
    try:
        table = db.get_table(table_name)
        all_items = query_by_account_ids(table, account_ids)

        dates = set()
        for item in all_items:
            sk = item.get(sk_field, "")
            parts = sk.split("#")
            for part in parts:
                try:
                    date.fromisoformat(part)
                    dates.add(part)
                    break
                except (ValueError, TypeError):
                    continue
        if dates:
            return date.fromisoformat(max(dates))
    except Exception as e:
        logger.debug("Snapshot date lookup failed for %s: %s", report_type, e)

    return date.today()


def compile_and_execute(
    spec: ReportSpec,
    account_ids: list[int],
    db,
) -> dict:
    """Validate a ReportSpec and execute the corresponding DynamoDB query.

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
    snapshot_date = _resolve_snapshot_date(report_type, account_ids, db)

    # Build params for the query function
    sort_field = spec.metric
    if sort_field not in template_def.get("allowed_sort_fields", [spec.metric]):
        sort_field = template_def.get("default_sort_field", "revenue")
    # Defense-in-depth: ensure sort_field is a bare identifier
    if not _re.match(r"^[a-z_]+$", sort_field):
        sort_field = template_def.get("default_sort_field", "revenue")

    params = {
        "start_date": start_date,
        "end_date": end_date,
        "limit": spec.limit,
        "snapshot_date": snapshot_date,
        "threshold": spec.threshold,
        "horizon_days": spec.horizon_days,
        "sort_field": sort_field,
        "sort_dir": spec.sort,
    }

    # Call the DynamoDB query function
    query_fn = template_def["fn"]
    result = query_fn(db, account_ids, params)

    time_desc = f"{start_date.isoformat()} to {end_date.isoformat()}"
    return {
        "columns": result["columns"],
        "rows": result["rows"],
        "report_type": report_type,
        "time_range": time_desc,
    }
