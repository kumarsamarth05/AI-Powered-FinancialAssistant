from fastapi import APIRouter

from backend.analytics.risk import calculate_risk_score

router = APIRouter()


@router.get("/{user_id}")
async def get_risk(user_id: str):
    return await calculate_risk_score(user_id)
