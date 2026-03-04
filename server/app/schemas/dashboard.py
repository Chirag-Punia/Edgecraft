from pydantic import BaseModel


class KPIData(BaseModel):
    title: str
    value: str
    change: str
    change_type: str  # positive | negative | neutral


class DashboardKPIs(BaseModel):
    kpis: list[KPIData]
