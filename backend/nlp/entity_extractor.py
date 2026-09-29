import re
from typing import Dict

AMOUNT_PATTERN = re.compile(
    r"(?:Rs\.?|INR|USD|\$|₹)?\s*(\d+(?:,\d{2,3})*(?:\.\d+)?)\s*(crore|lakh|k|thousand)?",
    re.IGNORECASE,
)

TIMEFRAMES = {
    "this week": "current_week",
    "current week": "current_week",
    "last week": "previous_week",
    "this month": "current_month",
    "current month": "current_month",
    "last month": "previous_month",
    "previous month": "previous_month",
    "last 30 days": "last_30_days",
    "last 90 days": "last_90_days",
    "this year": "current_year",
    "last year": "previous_year",
}

CATEGORIES = {
    "food": ["food", "restaurant", "groceries", "swiggy", "zomato"],
    "rent": ["rent", "apartment", "pg", "housing"],
    "transport": ["uber", "ola", "petrol", "fuel", "metro", "transport"],
    "entertainment": ["netflix", "movie", "gaming", "spotify", "entertainment"],
    "medical": ["hospital", "medicine", "doctor", "pharmacy", "medical"],
    "shopping": ["shopping", "amazon", "flipkart", "clothes"],
    "utilities": ["electricity", "water bill", "internet", "mobile bill", "utility"],
}


def extract_entities(text: str) -> Dict:
    lower_text = text.lower()
    result = {"amounts": [], "timeframe": None, "category": None, "raw": text}

    for match in AMOUNT_PATTERN.finditer(text):
        raw_number = match.group(1)
        suffix = (match.group(2) or "").lower()
        value = _normalize(raw_number, suffix)
        if value > 0:
            result["amounts"].append({"raw": match.group(0).strip(), "value": value})

    for phrase, canonical in TIMEFRAMES.items():
        if phrase in lower_text:
            result["timeframe"] = canonical
            break

    for category, keywords in CATEGORIES.items():
        if any(keyword in lower_text for keyword in keywords):
            result["category"] = category
            break

    return result


def _normalize(number: str, suffix: str = "") -> float:
    try:
        value = float(number.replace(",", ""))
        multiplier = {"crore": 10_000_000, "lakh": 100_000, "k": 1_000, "thousand": 1_000}.get(suffix, 1)
        return value * multiplier
    except (TypeError, ValueError):
        return 0.0
