from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.dashboard import DashboardKPIs, KPIData

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=DashboardKPIs)
def get_kpis(current_user: User = Depends(get_current_user)):
    """Return placeholder KPI data. Will be computed from real data after marketplace sync is built."""
    return DashboardKPIs(
        kpis=[
            KPIData(title="Today's GMV", value="₹1,24,560", change="+12.5% from yesterday", change_type="positive"),
            KPIData(title="Net Sales (30D)", value="₹28,75,000", change="+8.2% from yesterday", change_type="positive"),
            KPIData(title="Orders Today", value="186", change="+18 from yesterday", change_type="positive"),
            KPIData(title="Units Today", value="342", change="+24 from yesterday", change_type="positive"),
            KPIData(title="Return Rate", value="3.8%", change="+1.0% from yesterday", change_type="negative"),
            KPIData(title="Stockout Risks", value="5", change="Critical from yesterday", change_type="negative"),
        ]
    )
