from fastapi import APIRouter, Query

from backend.db.mongo import get_collection

router = APIRouter()


@router.get("/{user_id}")
async def get_history(user_id: str, category: str | None = None, limit: int = Query(200, ge=1, le=2000)):
    query = {"user_id": user_id}
    if category:
        query["category"] = category.strip().lower()

    cursor = get_collection("transactions").find(query).sort("date", -1).limit(limit)
    data = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        data.append(doc)
    return data
