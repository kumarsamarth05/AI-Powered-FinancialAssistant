from backend.nlp.intent_classifier import classify_intent
from backend.nlp.entity_extractor import extract_entities
from backend.nlp.sentiment import analyze_sentiment


def analyze_message(text: str) -> dict:
    """
    Runs all NLP components safely and returns a unified response.
    Fully defensive against model failures and bad outputs.
    """

    # ---------------- EMPTY INPUT ----------------
    if not text or not text.strip():
        return {
            "intent": "general_question",
            "confidence": 0.0,
            "all_intent_scores": {},
            "entities": {},
            "sentiment": {
                "sentiment": "neutral",
                "confidence": 0.0,
                "urgency": "low",
            },
        }

    try:
        # ---------------- INTENT ----------------
        try:
            intent_result = classify_intent(text) or {}
        except Exception:
            intent_result = {}

        intent = intent_result.get("intent", "general_question")
        confidence = float(intent_result.get("confidence", 0.0))
        all_scores = intent_result.get("all_scores", {}) or {}

        # ---------------- ENTITIES ----------------
        try:
            entities = extract_entities(text) or {}
        except Exception:
            entities = {}

        # ---------------- SENTIMENT ----------------
        try:
            sentiment = analyze_sentiment(text) or {}
        except Exception:
            sentiment = {}

        # ---------------- SAFE SENTIMENT STRUCTURE ----------------
        sentiment = {
            "sentiment": sentiment.get("sentiment", "neutral"),
            "confidence": float(sentiment.get("confidence", 0.0)),
            "urgency": sentiment.get("urgency", "low"),
        }

        # ---------------- FINAL OUTPUT ----------------
        return {
            "intent": intent,
            "confidence": confidence,
            "all_intent_scores": all_scores,
            "entities": entities,
            "sentiment": sentiment,
        }

    except Exception as e:
        # ---------------- HARD FAIL SAFE ----------------
        return {
            "intent": "general_question",
            "confidence": 0.0,
            "all_intent_scores": {},
            "entities": {},
            "sentiment": {
                "sentiment": "neutral",
                "confidence": 0.0,
                "urgency": "low",
            },
            "error": str(e),
        }