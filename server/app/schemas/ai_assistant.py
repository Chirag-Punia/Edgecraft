from datetime import datetime
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: int | None = None
    message: str = Field(..., min_length=1, max_length=2000)
    language: str | None = None


class ReportData(BaseModel):
    columns: list[str]
    rows: list[list]
    report_type: str
    time_range: str


class ChartSeries(BaseModel):
    name: str
    data_key: str
    color: str | None = None


class ChartData(BaseModel):
    chart_type: str  # "line" | "bar" | "pie" | "stacked_bar" | "grouped_bar"
    title: str
    x_key: str
    series: list[ChartSeries]
    x_label: str | None = None
    y_label: str | None = None
    currency_axis: bool = False


class WebSource(BaseModel):
    title: str
    url: str


class ChatResponse(BaseModel):
    session_id: int
    message_id: int | None
    content: str
    report_data: ReportData | None = None
    chart_data: ChartData | None = None
    web_sources: list[WebSource] = []
    suggested_questions: list[str] = []
    language: str = "en"


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    report_data: ReportData | None = None
    chart_data: ChartData | None = None
    web_sources: list[WebSource] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionResponse(BaseModel):
    id: int
    title: str | None
    language: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ExportRequest(BaseModel):
    message_id: int


class ExportResponse(BaseModel):
    csv_data: str
    filename: str
