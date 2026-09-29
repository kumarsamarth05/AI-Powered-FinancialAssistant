from fastapi import APIRouter, Query

from backend.analytics.forecast import forecast_expenses

router = APIRouter()


@router.get("/{user_id}")
async def forecast(user_id: str, days: int = Query(30, ge=1, le=365)):
    return await forecast_expenses(user_id, days)
