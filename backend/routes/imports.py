import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend.db.mongo import get_collection

router = APIRouter()


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_date(value: str | None):
    if not value:
        return utc_now()
    text = value.strip()
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise ValueError(f"Unsupported date: {text}") from exc


@router.post("/csv", status_code=status.HTTP_201_CREATED)
async def import_transactions_csv(
    user_id: str = Form(..., min_length=1, max_length=100),
    file: UploadFile = File(...),
):
    filename = (file.filename or "transactions.csv").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file")

    raw = await file.read()
    if len(raw) > 2_000_000:
        raise HTTPException(status_code=413, detail="CSV must be 2 MB or smaller")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must use UTF-8 encoding")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV is empty or missing a header row")

    required = {"amount"}
    normalized_fields = {str(name).strip().lower() for name in reader.fieldnames if name}
    missing = required - normalized_fields
    if missing:
        raise HTTPException(status_code=400, detail="CSV must include an amount column")

    documents = []
    errors = []
    now = utc_now()

    for row_number, raw_row in enumerate(reader, start=2):
        row = {str(k).strip().lower(): (v or "").strip() for k, v in raw_row.items() if k}
        if not any(row.values()):
            continue
        try:
            amount = float(row.get("amount", "").replace(",", ""))
            if amount <= 0:
                raise ValueError("amount must be greater than zero")
            transaction_type = (row.get("transaction_type") or row.get("type") or "debit").lower()
            if transaction_type not in {"debit", "credit"}:
                raise ValueError("type must be debit or credit")
            documents.append(
                {
                    "user_id": user_id,
                    "amount": amount,
                    "category": (row.get("category") or "other").lower(),
                    "description": row.get("description") or "",
                    "merchant": row.get("merchant") or None,
                    "date": parse_date(row.get("date")),
                    "transaction_type": transaction_type,
                    "tags": [],
                    "created_at": now,
                }
            )
        except Exception as exc:
            errors.append({"row": row_number, "error": str(exc)})

    if not documents:
        raise HTTPException(status_code=400, detail={"message": "No valid transactions found", "errors": errors[:10]})

    await get_collection("transactions").insert_many(documents)
    return {
        "message": "CSV imported",
        "imported": len(documents),
        "skipped": len(errors),
        "errors": errors[:10],
    }
