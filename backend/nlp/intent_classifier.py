import os
from functools import lru_cache

from loguru import logger

INTENT_LABELS = [
    "expense_concern",
    "loan_inquiry",
    "fraud_alert",
    "investment_query",
    "budget_planning",
    "general_question",
]

KEYWORDS = {
    "fraud_alert": ["fraud", "suspicious", "unauthorized", "not mine", "unknown transaction", "scam"],
    "loan_inquiry": ["loan", "emi", "interest rate", "home loan", "car loan", "borrow"],
    "investment_query": ["invest", "investment", "mutual fund", "index fund", "fd", "stocks", "sip"],
    "budget_planning": ["budget", "save money", "saving plan", "monthly limit", "spending limit"],
    "expense_concern": ["spent", "spending", "expense", "expenses", "too much", "how much", "category"],
}


@lru_cache(maxsize=1)
def load_classifier():
    if os.getenv("USE_TRANSFORMERS", "false").lower() not in {"1", "true", "yes"}:
        return None
    try:
        from transformers import pipeline
        logger.info("Loading zero-shot intent classifier...")
        return pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=-1)
    except Exception as exc:
        logger.warning(f"Transformer intent model unavailable; using keyword fallback: {exc}")
        return None


def _keyword_classify(text: str) -> dict:
    lower = text.lower()
    scores = {label: 0.0 for label in INTENT_LABELS}
    best_intent = "general_question"
    best_hits = 0
    for intent, keywords in KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in lower)
        scores[intent] = min(0.95, 0.55 + hits * 0.12) if hits else 0.0
        if hits > best_hits:
            best_hits = hits
            best_intent = intent
    if best_hits == 0:
        scores["general_question"] = 0.65
    return {
        "intent": best_intent,
        "confidence": round(scores[best_intent] or 0.65, 3),
        "all_scores": scores,
    }


def classify_intent(text: str) -> dict:
    if not text or not text.strip():
        return {"intent": "general_question", "confidence": 0.0, "all_scores": {}}

    classifier = load_classifier()
    if classifier is None:
        return _keyword_classify(text)

    try:
        result = classifier(text, candidate_labels=INTENT_LABELS, multi_label=False)
        return {
            "intent": result["labels"][0],
            "confidence": round(float(result["scores"][0]), 3),
            "all_scores": {label: round(float(score), 3) for label, score in zip(result["labels"], result["scores"])},
        }
    except Exception as exc:
        logger.warning(f"Intent classification failed; using keyword fallback: {exc}")
        return _keyword_classify(text)
