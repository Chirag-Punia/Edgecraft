"""AI Reports — pre-generated cross-domain insights powered by LLM."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from boto3.dynamodb.conditions import Key

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.dynamo.helpers import query_all, from_dynamo_item
from app.enums import AIReportType
from app.schemas.ai_reports import AIReportListResponse, AIReportSummary, AIReportDetail
from app.services.report_generator import REPORT_CONFIGS, generate_report

router = APIRouter(prefix="/ai-reports", tags=["ai-reports"])


@router.get("/", response_model=AIReportListResponse)
def list_reports(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all available AI report types with their cache status."""
    seller_id = current_user.seller_id
    if not seller_id:
        return AIReportListResponse(reports=[
            AIReportSummary(
                report_type=rt, title=cfg["title"], description=cfg["description"],
                generated_at=None, is_stale=True, status="not_generated",
            )
            for rt, cfg in REPORT_CONFIGS.items()
        ])

    # Query all reports for this seller from DynamoDB
    reports_table = db.get_table("ai_reports")
    cached_items = query_all(reports_table,
                             KeyConditionExpression=Key("seller_id").eq(seller_id))
    cached = {r.get("report_type"): r for r in cached_items}

    reports = []
    for rt, cfg in REPORT_CONFIGS.items():
        existing = cached.get(rt)
        is_stale = True
        status = "not_generated"
        generated_at = None
        if existing:
            generated_at = existing.get("generated_at")
            status = existing.get("status", "not_generated")
            if (existing.get("status") == "ready"
                    and existing.get("expires_at")
                    and existing["expires_at"] > datetime.utcnow().isoformat()):
                is_stale = False

        reports.append(AIReportSummary(
            report_type=rt, title=cfg["title"], description=cfg["description"],
            generated_at=generated_at, is_stale=is_stale, status=status,
        ))

    return AIReportListResponse(reports=reports)


@router.get("/{report_type}", response_model=AIReportDetail)
def get_report(
    report_type: AIReportType,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a specific AI report. Returns cached if fresh, generates if stale."""
    rt = report_type.value
    seller_id = current_user.seller_id
    if not seller_id:
        raise HTTPException(status_code=400, detail="No seller profile. Complete business setup first.")

    config = REPORT_CONFIGS[rt]
    report = generate_report(db, seller_id, rt)

    # report may be a dict or SimpleNamespace
    ai_narrative = report.ai_narrative if hasattr(report, 'ai_narrative') else report.get("ai_narrative", "")
    report_data = report.report_data if hasattr(report, 'report_data') else report.get("report_data")
    score = report.score if hasattr(report, 'score') else report.get("score")
    generated_at = report.generated_at if hasattr(report, 'generated_at') else report.get("generated_at")
    report_status = report.status if hasattr(report, 'status') else report.get("status")

    return AIReportDetail(
        report_type=rt,
        title=config["title"],
        ai_narrative=ai_narrative or "",
        report_data=report_data,
        score=score,
        generated_at=generated_at,
        status=report_status,
    )


@router.post("/{report_type}/refresh", response_model=AIReportDetail)
def refresh_report(
    report_type: AIReportType,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Force-regenerate a report (5-min cooldown per report type)."""
    rt = report_type.value
    seller_id = current_user.seller_id
    if not seller_id:
        raise HTTPException(status_code=400, detail="No seller profile.")

    # Rate limit: 5-min cooldown per report
    # Check if there's a recent ready report for this seller + report_type
    reports_table = db.get_table("ai_reports")
    # The SK is report_type_lang, which is report_type#language
    # We need to check all language variants
    all_reports = query_all(reports_table,
                            KeyConditionExpression=Key("seller_id").eq(seller_id)
                            & Key("report_type_lang").begins_with(f"{rt}#"))
    cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
    for r in all_reports:
        if (r.get("status") == "ready"
                and r.get("generated_at")
                and r["generated_at"] > cutoff):
            raise HTTPException(status_code=429, detail="Please wait 5 minutes between refreshes.")

    config = REPORT_CONFIGS[rt]
    report = generate_report(db, seller_id, rt, force=True)

    ai_narrative = report.ai_narrative if hasattr(report, 'ai_narrative') else report.get("ai_narrative", "")
    report_data = report.report_data if hasattr(report, 'report_data') else report.get("report_data")
    score = report.score if hasattr(report, 'score') else report.get("score")
    generated_at = report.generated_at if hasattr(report, 'generated_at') else report.get("generated_at")
    report_status = report.status if hasattr(report, 'status') else report.get("status")

    return AIReportDetail(
        report_type=rt,
        title=config["title"],
        ai_narrative=ai_narrative or "",
        report_data=report_data,
        score=score,
        generated_at=generated_at,
        status=report_status,
    )
