from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from backend.analytics.spending import _load_user_transactions, _normalize_docs, utc_now


async def forecast_expenses(user_id: str, days: int = 30) -> dict:
    raw_docs = await _load_user_transactions(user_id)
    docs = _normalize_docs(raw_docs, datetime(1970, 1, 1), utc_now())

    if len(docs) < 7:
        return {
            "forecast": [],
            "predicted_total": 0.0,
            "days": days,
            "message": "Need at least 7 debit transactions",
        }

    df = pd.DataFrame(docs)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["date", "amount"])
    if len(df) < 7:
        return {
            "forecast": [],
            "predicted_total": 0.0,
            "days": days,
            "message": "Need at least 7 valid debit transactions",
        }

    daily = df.groupby(df["date"].dt.date)["amount"].sum().reset_index()
    daily.columns = ["date", "spent"]
    if len(daily) < 3:
        return {
            "forecast": [],
            "predicted_total": 0.0,
            "days": days,
            "message": "Need transactions across at least 3 different days",
        }

    daily["day_number"] = np.arange(len(daily))
    model = LinearRegression().fit(daily[["day_number"]], daily["spent"])
    future_days = np.arange(len(daily), len(daily) + days).reshape(-1, 1)
    predictions = np.maximum(0, model.predict(future_days))
    last_date = daily["date"].max()

    forecast = [
        {
            "date": str(last_date + timedelta(days=i + 1)),
            "predicted_spending": round(float(amount), 2),
        }
        for i, amount in enumerate(predictions)
    ]
    return {
        "forecast": forecast,
        "predicted_total": round(float(np.sum(predictions)), 2),
        "days": days,
        "message": "Linear trend forecast from normalized debit transaction history",
    }
