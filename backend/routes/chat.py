import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.analytics.spending import detect_anomalies, get_spending_analysis
from backend.db.models import ChatRequest, ChatResponse, IntentType, Sentiment
from backend.db.mongo import get_collection
from backend.nlp.orchestrator import analyze_message

router = APIRouter()
logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        nlp = analyze_message(req.message) or {}
        raw_intent = nlp.get("intent", "general_question")
        try:
            intent = IntentType(raw_intent)
        except ValueError:
            intent = IntentType.general_question

        sentiment_data = nlp.get("sentiment") or {}
        sentiment = Sentiment(
            sentiment=str(sentiment_data.get("sentiment", "neutral")),
            confidence=float(sentiment_data.get("confidence") or 0.0),
            urgency=str(sentiment_data.get("urgency", "low")),
        )

        response = await _route_intent(intent.value, req.user_id, nlp)

        try:
            await get_collection("conversations").insert_one({
                "user_id": req.user_id,
                "message": req.message,
                "intent": intent.value,
                "confidence": float(nlp.get("confidence") or 0.0),
                "timestamp": utc_now(),
            })
        except Exception as db_exc:
            logger.warning("Conversation logging failed: %s", db_exc)

        return ChatResponse(
            intent=intent,
            confidence=float(nlp.get("confidence") or 0.0),
            entities=nlp.get("entities") or {},
            sentiment=sentiment,
            **response,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Chat endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail="Chat processing failed")


async def _route_intent(intent: str, user_id: str, nlp: dict) -> dict:
    entities = nlp.get("entities") or {}
    period = entities.get("timeframe") or "current_month"

    if intent == "expense_concern":
        analysis = await get_spending_analysis(user_id, period)
        anomalies = await detect_anomalies(user_id)
        categories = analysis.get("by_category", {}) or {}
        top_cat = next(iter(categories), "no category yet")
        safe_period = str(period).replace("_", " ")
        return {
            "response_text": (
                f"For {safe_period}, your total spending is ₹{analysis.get('total_spent', 0):,.2f}. "
                f"Your highest spending category is {top_cat}."
            ),
            "chart_data": {
                "type": "spending",
                "category_chart": categories,
                "trend_chart": analysis.get("daily_trend", []),
            },
            "alerts": [
                f"Unusual ₹{item.get('amount', 0):,.2f} transaction at {item.get('merchant', 'Unknown')}"
                for item in anomalies[:3]
            ],
            "suggestions": ["Review your top spending category", "Set a monthly category budget"],
        }

    if intent == "fraud_alert":
        anomalies = await detect_anomalies(user_id)
        if anomalies:
            first = anomalies[0]
            text = (
                f"I found {len(anomalies)} unusual transaction(s) in the recent data. "
                f"The strongest anomaly is ₹{first.get('amount', 0):,.2f} at {first.get('merchant', 'Unknown')}."
            )
        else:
            text = "I did not detect a strong statistical anomaly in the recent transaction history."
        return {
            "response_text": text,
            "chart_data": {"type": "anomalies", "items": anomalies[:10]},
            "alerts": ["If a transaction is not yours, contact your bank/card issuer immediately."],
            "suggestions": ["Review recent transactions", "Freeze the affected card if necessary"],
        }

    if intent == "budget_planning":
        analysis = await get_spending_analysis(user_id, "current_month")
        total = float(analysis.get("total_spent", 0) or 0)
        suggested = round(total * 0.9, 2) if total else 0.0
        text = (
            f"You have spent ₹{total:,.2f} this month. A simple starting target is ₹{suggested:,.2f} "
            "for next month, then refine category limits based on your priorities."
            if total
            else "Add some transactions first and I can suggest a practical monthly budget from your spending pattern."
        )
        return {
            "response_text": text,
            "chart_data": {"type": "budget", "by_category": analysis.get("by_category", {})},
            "alerts": [],
            "suggestions": ["Create category limits", "Track savings as a separate monthly goal"],
        }

    if intent == "loan_inquiry":
        return {
            "response_text": (
                "For a loan decision, compare the interest rate, EMI, processing fee, tenure, prepayment rules, "
                "and total repayment amount. I can also help you estimate affordability using your monthly spending data."
            ),
            "chart_data": None,
            "alerts": [],
            "suggestions": ["Keep EMI within a comfortable share of monthly income", "Compare total cost, not only EMI"],
        }

    if intent == "investment_query":
        return {
            "response_text": (
                "Investment choices depend on time horizon, liquidity needs, and risk tolerance. "
                "For long-term goals, diversified options can be compared with lower-risk products such as fixed deposits."
            ),
            "chart_data": None,
            "alerts": [],
            "suggestions": ["Define your time horizon", "Keep an emergency fund before taking higher investment risk"],
        }

    return {
        "response_text": "I can help with spending analysis, budgets, unusual transactions, loans, investments, risk, and forecasts.",
        "chart_data": None,
        "alerts": [],
        "suggestions": ["Show my monthly spending", "Check unusual transactions", "Forecast my expenses"],
    }
