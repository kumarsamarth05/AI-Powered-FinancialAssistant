from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from backend.db.mongo import get_collection


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _empty(period: str, error: str | None = None) -> dict:
    data = {
        "total_spent": 0.0,
        "by_category": {},
        "daily_trend": [],
        "daily_average": 0.0,
        "transaction_count": 0,
        "vs_previous_period_pct": 0.0,
        "period": period,
    }
    if error:
        data["error"] = error
    return data


def _coerce_datetime(value: Any) -> datetime | None:
    """Convert Mongo/Pydantic/legacy string dates into naive UTC datetimes."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    try:
        parsed = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime().astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


def _coerce_amount(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            value = (
                value.replace("₹", "")
                .replace("INR", "")
                .replace(",", "")
                .strip()
            )
        amount = float(value)
        if not np.isfinite(amount):
            return None
        return abs(amount)
    except (TypeError, ValueError):
        return None


def _normalized_transaction_type(doc: dict) -> str:
    raw = (
        doc.get("transaction_type")
        or doc.get("type")
        or doc.get("txn_type")
        or doc.get("kind")
        or ""
    )
    value = str(raw).strip().lower()
    if value in {"debit", "expense", "spent", "spend", "withdrawal", "dr"}:
        return "debit"
    if value in {"credit", "income", "deposit", "salary", "refund", "cr"}:
        return "credit"

    # Older project versions sometimes stored no explicit type.
    # Infer obvious income categories; otherwise treat the record as spending.
    category = str(doc.get("category") or "").strip().lower()
    if category in {"income", "salary", "stipend", "refund", "interest", "cashback"}:
        return "credit"
    return "debit"


def _normalize_docs(
    docs: Iterable[dict],
    start: datetime,
    end: datetime,
    *,
    debit_only: bool = True,
) -> List[dict]:
    normalized: List[dict] = []
    for doc in docs:
        if debit_only and _normalized_transaction_type(doc) != "debit":
            continue
        dt = _coerce_datetime(doc.get("date") or doc.get("transaction_date") or doc.get("created_at"))
        if dt is None or dt < start or dt > end:
            continue
        amount = _coerce_amount(doc.get("amount"))
        if amount is None or amount <= 0:
            continue
        category = str(doc.get("category") or "other").strip().lower() or "other"
        normalized.append(
            {
                "amount": amount,
                "category": category,
                "date": dt,
                "merchant": doc.get("merchant") or doc.get("description") or "Unknown",
            }
        )
    return normalized


async def _load_user_transactions(user_id: str, limit: int = 20_000) -> List[dict]:
    """Load user transactions without a brittle Mongo date/type filter.

    This intentionally normalizes legacy schemas in Python so analytics keeps working
    for older FinanceAI records that used string dates or a `type` field.
    """
    col = get_collection("transactions")
    cursor = col.find(
        {"user_id": user_id},
        projection={
            "_id": 0,
            "amount": 1,
            "category": 1,
            "date": 1,
            "transaction_date": 1,
            "created_at": 1,
            "merchant": 1,
            "description": 1,
            "transaction_type": 1,
            "type": 1,
            "txn_type": 1,
            "kind": 1,
        },
    )
    return await cursor.to_list(length=limit)


async def get_spending_analysis(user_id: str, period: str = "current_month") -> dict:
    try:
        start, end = _date_range(period)
        raw_docs = await _load_user_transactions(user_id)
        docs = _normalize_docs(raw_docs, start, end)
        if not docs:
            return _empty(period)

        df = pd.DataFrame(docs)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df = df.dropna(subset=["date", "amount"])
        if df.empty:
            return _empty(period)

        df["category"] = df["category"].fillna("other").astype(str).str.lower()
        df["day"] = df["date"].dt.date

        by_category = (
            df.groupby("category")["amount"]
            .sum()
            .sort_values(ascending=False)
            .round(2)
            .to_dict()
        )

        daily = df.groupby("day")["amount"].sum().reset_index()
        daily.columns = ["date", "spent"]
        daily["date"] = daily["date"].astype(str)
        daily["spent"] = daily["spent"].round(2)
        daily["moving_avg"] = daily["spent"].rolling(7, min_periods=1).mean().round(2)

        total_spent = float(df["amount"].sum())
        prev_start, prev_end = _previous_period_range(start, end)
        prev_docs = _normalize_docs(raw_docs, prev_start, prev_end)
        prev_total = sum(float(d.get("amount", 0) or 0) for d in prev_docs)
        pct_change = ((total_spent - prev_total) / prev_total * 100) if prev_total > 0 else 0.0

        active_days = max(1, (end.date() - start.date()).days + 1)
        return {
            "total_spent": round(total_spent, 2),
            "by_category": {str(k): float(v) for k, v in by_category.items()},
            "daily_trend": daily.to_dict(orient="records"),
            "daily_average": round(total_spent / active_days, 2),
            "transaction_count": int(len(df)),
            "vs_previous_period_pct": round(float(pct_change), 2),
            "period": period,
        }
    except Exception as exc:
        return _empty(period, str(exc))


def _date_range(period: str) -> Tuple[datetime, datetime]:
    now = utc_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_end = current_month_start - timedelta(microseconds=1)
    previous_month_start = previous_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_week_start = today_start - timedelta(days=today_start.weekday())
    current_year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_year_start = current_year_start.replace(year=current_year_start.year - 1)
    previous_year_end = current_year_start - timedelta(microseconds=1)

    ranges = {
        "current_week": (current_week_start, now),
        "previous_week": (current_week_start - timedelta(days=7), current_week_start - timedelta(microseconds=1)),
        "current_month": (current_month_start, now),
        "previous_month": (previous_month_start, previous_month_end),
        "last_30_days": (now - timedelta(days=30), now),
        "last_90_days": (now - timedelta(days=90), now),
        "current_year": (current_year_start, now),
        "previous_year": (previous_year_start, previous_year_end),
    }
    return ranges.get(period, ranges["current_month"])


def _previous_period_range(start: datetime, end: datetime) -> Tuple[datetime, datetime]:
    duration = end - start
    prev_end = start - timedelta(microseconds=1)
    prev_start = prev_end - duration
    return prev_start, prev_end


async def detect_anomalies(user_id: str) -> List[Dict]:
    try:
        raw_docs = await _load_user_transactions(user_id)
        end = utc_now()
        start = end - timedelta(days=30)
        docs = _normalize_docs(raw_docs, start, end)
        if len(docs) < 5:
            return []

        df = pd.DataFrame(docs)
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["category"] = df["category"].fillna("other")
        df = df.dropna(subset=["amount"])

        anomalies: List[Dict] = []
        for category, group in df.groupby("category"):
            if len(group) < 3:
                continue
            mean = float(group["amount"].mean())
            std = float(group["amount"].std())
            if std == 0 or np.isnan(std):
                continue
            z_scores = np.abs((group["amount"] - mean) / std)
            for idx, row in group[z_scores > 2.0].iterrows():
                anomalies.append(
                    {
                        "category": str(category),
                        "amount": round(float(row["amount"]), 2),
                        "merchant": row.get("merchant") or "Unknown",
                        "date": str(row["date"].date()) if pd.notnull(row["date"]) else "",
                        "z_score": round(float(z_scores.loc[idx]), 2),
                        "category_avg": round(mean, 2),
                    }
                )
        return sorted(anomalies, key=lambda item: item["z_score"], reverse=True)
    except Exception:
        return []
