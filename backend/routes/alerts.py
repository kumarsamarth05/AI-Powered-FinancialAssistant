from fastapi import APIRouter
from backend.analytics.spending import detect_anomalies

router = APIRouter()


@router.get("/{user_id}")
async def get_alerts(user_id: str):
    alerts = await detect_anomalies(user_id)
    return {"alerts": alerts}