import asyncio
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter

from backend.analytics.forecast import forecast_expenses
from backend.analytics.risk import calculate_risk_score
from backend.analytics.spending import detect_anomalies, get_spending_analysis

router = APIRouter()
Period = Literal[
    "current_week",
    "previous_week",
    "current_month",
    "previous_month",
    "last_30_days",
    "last_90_days",
    "current_year",
    "previous_year",
]


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/{user_id}")
async def live_snapshot(user_id: str, period: Period = "current_month"):
    analysis, anomalies, risk, forecast = await asyncio.gather(
        get_spending_analysis(user_id, period),
        detect_anomalies(user_id),
        calculate_risk_score(user_id),
        forecast_expenses(user_id, 30),
    )
    return {
        "user_id": user_id,
        "period": period,
        "analysis": analysis,
        "alerts": anomalies[:10],
        "risk": risk,
        "forecast": forecast,
        "generated_at": utc_iso(),
    }
