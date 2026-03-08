from datetime import datetime
from pydantic import BaseModel


class AIReportSummary(BaseModel):
    report_type: str
    title: str
    description: str
    generated_at: datetime | None
    is_stale: bool
    status: str


class AIReportListResponse(BaseModel):
    reports: list[AIReportSummary]


class AIReportDetail(BaseModel):
    report_type: str
    title: str
    ai_narrative: str
    report_data: dict | None = None
    score: int | None = None
    generated_at: datetime | None
    status: str
