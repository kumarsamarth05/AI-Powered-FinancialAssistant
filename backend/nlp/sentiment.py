import os
from functools import lru_cache

from loguru import logger

NEGATIVE_WORDS = {"worried", "bad", "fraud", "suspicious", "problem", "overspent", "stolen", "unauthorized", "urgent"}
POSITIVE_WORDS = {"good", "great", "happy", "saved", "profit", "excellent"}


@lru_cache(maxsize=1)
def load_sentiment():
    if os.getenv("USE_TRANSFORMERS", "false").lower() not in {"1", "true", "yes"}:
        return None
    try:
        from transformers import pipeline
        logger.info("Loading sentiment model...")
        return pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english", device=-1)
    except Exception as exc:
        logger.warning(f"Transformer sentiment model unavailable; using rule fallback: {exc}")
        return None


def _rule_sentiment(text: str) -> dict:
    lower = text.lower()
    negative_hits = sum(1 for word in NEGATIVE_WORDS if word in lower)
    positive_hits = sum(1 for word in POSITIVE_WORDS if word in lower)
    if negative_hits > positive_hits:
        urgency = "high" if any(word in lower for word in {"fraud", "stolen", "unauthorized", "urgent"}) else "medium"
        return {"sentiment": "negative", "confidence": min(0.9, 0.6 + negative_hits * 0.08), "urgency": urgency}
    if positive_hits > negative_hits:
        return {"sentiment": "positive", "confidence": min(0.9, 0.6 + positive_hits * 0.08), "urgency": "low"}
    return {"sentiment": "neutral", "confidence": 0.55, "urgency": "low"}


def analyze_sentiment(text: str) -> dict:
    if not text or not text.strip():
        return {"sentiment": "neutral", "confidence": 0.0, "urgency": "low"}

    model = load_sentiment()
    if model is None:
        return _rule_sentiment(text)

    try:
        result = model(text[:512])[0]
        label = str(result.get("label", "neutral")).lower()
        score = float(result.get("score", 0.0))
        urgency = "high" if label == "negative" and score > 0.90 else "medium" if label == "negative" and score > 0.75 else "low"
        return {"sentiment": label, "confidence": round(score, 3), "urgency": urgency}
    except Exception as exc:
        logger.warning(f"Sentiment analysis failed; using rule fallback: {exc}")
        return _rule_sentiment(text)
