from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, status

from backend.db.models import TransactionCreate
from backend.db.mongo import get_collection

router = APIRouter()


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def serialize(doc: dict) -> dict:
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_transaction(transaction: TransactionCreate):
    col = get_collection("transactions")
    payload = transaction.model_dump()
    payload["created_at"] = utc_now()
    result = await col.insert_one(payload)
    return {"message": "Transaction added", "id": str(result.inserted_id)}


@router.get("/{user_id}")
async def get_transactions(user_id: str, limit: int = Query(100, ge=1, le=1000)):
    col = get_collection("transactions")
    cursor = col.find({"user_id": user_id}).sort("date", -1).limit(limit)
    return [serialize(doc) async for doc in cursor]


@router.delete("/{transaction_id}")
async def delete_transaction(transaction_id: str):
    if not ObjectId.is_valid(transaction_id):
        raise HTTPException(status_code=400, detail="Invalid transaction id")
    result = await get_collection("transactions").delete_one({"_id": ObjectId(transaction_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Transaction deleted"}
