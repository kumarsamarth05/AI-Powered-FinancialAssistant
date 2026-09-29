from backend.analytics.spending import detect_anomalies, get_spending_analysis


async def calculate_risk_score(user_id: str) -> dict:
    anomalies = await detect_anomalies(user_id)
    analysis = await get_spending_analysis(user_id, "current_month")

    anomaly_score = min(35.0, len(anomalies) * 7.0)
    trend = float(analysis.get("vs_previous_period_pct", 0) or 0)
    trend_score = min(30.0, max(0.0, trend * 0.3))

    high_risk_categories = {"gambling", "crypto", "unknown"}
    by_category = analysis.get("by_category", {}) or {}
    risky_spend = sum(float(v) for k, v in by_category.items() if str(k).lower() in high_risk_categories)
    total_spent = float(analysis.get("total_spent", 0) or 0)
    category_score = min(35.0, (risky_spend / total_spent) * 100.0) if total_spent > 0 else 0.0

    total_score = min(100.0, anomaly_score + trend_score + category_score)
    level = "low" if total_score < 30 else "medium" if total_score < 60 else "high"
    return {
        "score": round(total_score),
        "level": level,
        "anomaly_count": len(anomalies),
        "factors": {
            "anomaly_score": round(anomaly_score, 1),
            "spending_trend_score": round(trend_score, 1),
            "category_score": round(category_score, 1),
        },
    }
