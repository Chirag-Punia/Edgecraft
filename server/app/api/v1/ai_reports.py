"""AI Reports — pre-generated cross-domain insights powered by LLM."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.enums import AIReportType
from app.models.ai_report import AIReport
from app.models.user import User
from app.schemas.ai_reports import AIReportListResponse, AIReportSummary, AIReportDetail
from app.services.report_generator import REPORT_CONFIGS, generate_report

router = APIRouter(prefix="/ai-reports", tags=["ai-reports"])


@router.get("/", response_model=AIReportListResponse)
def list_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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

    cached = {
        r.report_type: r
        for r in db.query(AIReport).filter(AIReport.seller_id == seller_id).all()
    }

    reports = []
    for rt, cfg in REPORT_CONFIGS.items():
        existing = cached.get(rt)
        is_stale = True
        status = "not_generated"
        generated_at = None
        if existing:
            generated_at = existing.generated_at
            status = existing.status
            if existing.status == "ready" and existing.expires_at and existing.expires_at > datetime.utcnow():
                is_stale = False

        reports.append(AIReportSummary(
            report_type=rt, title=cfg["title"], description=cfg["description"],
            generated_at=generated_at, is_stale=is_stale, status=status,
        ))

    return AIReportListResponse(reports=reports)


@router.get("/{report_type}", response_model=AIReportDetail)
def get_report(
    report_type: AIReportType,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific AI report. Returns cached if fresh, generates if stale."""
    rt = report_type.value
    seller_id = current_user.seller_id
    if not seller_id:
        raise HTTPException(status_code=400, detail="No seller profile. Complete business setup first.")

    config = REPORT_CONFIGS[rt]
    report = generate_report(db, seller_id, rt)

    return AIReportDetail(
        report_type=rt,
        title=config["title"],
        ai_narrative=report.ai_narrative or "",
        report_data=report.report_data,
        score=report.score,
        generated_at=report.generated_at,
        status=report.status,
    )


@router.post("/{report_type}/refresh", response_model=AIReportDetail)
def refresh_report(
    report_type: AIReportType,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Force-regenerate a report (5-min cooldown per report type)."""
    rt = report_type.value
    seller_id = current_user.seller_id
    if not seller_id:
        raise HTTPException(status_code=400, detail="No seller profile.")

    # Rate limit: 5-min cooldown per report
    recent = (
        db.query(AIReport)
        .filter(AIReport.seller_id == seller_id, AIReport.report_type == rt,
                AIReport.status == "ready",
                AIReport.generated_at > datetime.utcnow() - timedelta(minutes=5))
        .first()
    )
    if recent:
        raise HTTPException(status_code=429, detail="Please wait 5 minutes between refreshes.")

    config = REPORT_CONFIGS[rt]
    report = generate_report(db, seller_id, rt, force=True)

    return AIReportDetail(
        report_type=rt,
        title=config["title"],
        ai_narrative=report.ai_narrative or "",
        report_data=report.report_data,
        score=report.score,
        generated_at=report.generated_at,
        status=report.status,
    )
