from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, status

from backend.db.models import GoalCreate, GoalProgressUpdate
from backend.db.mongo import get_collection

router = APIRouter()


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def serialize(doc: dict) -> dict:
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    return doc


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_goal(goal: GoalCreate):
    payload = goal.model_dump()
    payload["created_at"] = utc_now()
    result = await get_collection("goals").insert_one(payload)
    return {"message": "Goal created", "goal_id": str(result.inserted_id)}


@router.get("/{user_id}")
async def get_goals(user_id: str):
    cursor = get_collection("goals").find({"user_id": user_id}).sort("created_at", -1)
    return [serialize(goal) async for goal in cursor]


@router.delete("/item/{goal_id}")
async def delete_goal(goal_id: str):
    if not ObjectId.is_valid(goal_id):
        raise HTTPException(status_code=400, detail="Invalid goal id")
    result = await get_collection("goals").delete_one({"_id": ObjectId(goal_id)})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"message": "Goal deleted"}


@router.patch("/item/{goal_id}")
async def update_goal_progress(goal_id: str, update: GoalProgressUpdate):
    if not ObjectId.is_valid(goal_id):
        raise HTTPException(status_code=400, detail="Invalid goal id")
    result = await get_collection("goals").update_one(
        {"_id": ObjectId(goal_id)},
        {"$set": {"current_amount": update.current_amount, "updated_at": utc_now()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"message": "Goal progress updated", "current_amount": update.current_amount}
