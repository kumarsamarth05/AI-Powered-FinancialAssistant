from datetime import datetime, timedelta, timezone

from backend.analytics.spending import get_spending_analysis
from backend.db.mongo import get_collection

DEMO_USER_ID = "demo-user"

# days_ago, amount, category, merchant, type
DEMO_TRANSACTIONS = [
    (0, 210, "food", "Swiggy", "debit"),
    (1, 120, "food", "Zomato", "debit"),
    (2, 75, "transport", "Uber", "debit"),
    (3, 850, "shopping", "Amazon", "debit"),
    (4, 240, "food", "Groceries", "debit"),
    (5, 60, "transport", "Metro", "debit"),
    (6, 300, "shopping", "Local Store", "debit"),
    (7, 499, "entertainment", "Netflix", "debit"),
    (8, 350, "shopping", "Myntra", "debit"),
    (9, 180, "medical", "Pharmacy", "debit"),
    (10, 130, "food", "Zomato", "debit"),
    (11, 420, "shopping", "Flipkart", "debit"),
    (12, 90, "transport", "Ola", "debit"),
    (13, 500, "shopping", "Mall", "debit"),
    (14, 1500, "rent", "PG Rent", "debit"),
    (15, 450, "shopping", "Clothing Store", "debit"),
    (16, 220, "food", "Restaurant", "debit"),
    (18, 3800, "shopping", "Electronics Store", "debit"),
    (20, 5000, "income", "Internship Stipend", "credit"),
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def refresh_demo_data() -> dict:
    """Replace the reserved demo-user records with fresh rolling sample data."""
    now = utc_now()
    transactions = get_collection("transactions")
    goals = get_collection("goals")

    await transactions.delete_many({"user_id": DEMO_USER_ID})
    await goals.delete_many({"user_id": DEMO_USER_ID})

    docs = []
    for days_ago, amount, category, merchant, txn_type in DEMO_TRANSACTIONS:
        docs.append(
            {
                "user_id": DEMO_USER_ID,
                "amount": amount,
                "category": category,
                "description": merchant,
                "merchant": merchant,
                "date": now - timedelta(days=days_ago),
                "transaction_type": txn_type,
                "tags": ["demo"],
                "created_at": now,
            }
        )
    await transactions.insert_many(docs)

    await goals.insert_many(
        [
            {
                "user_id": DEMO_USER_ID,
                "name": "Emergency Fund",
                "target_amount": 50000,
                "current_amount": 18000,
                "deadline": now + timedelta(days=180),
                "created_at": now,
            },
            {
                "user_id": DEMO_USER_ID,
                "name": "New Laptop",
                "target_amount": 80000,
                "current_amount": 25000,
                "deadline": now + timedelta(days=240),
                "created_at": now,
            },
        ]
    )

    analysis = await get_spending_analysis(DEMO_USER_ID, "current_month")
    return {
        "user_id": DEMO_USER_ID,
        "inserted": len(docs),
        "current_month_transactions": analysis.get("transaction_count", 0),
        "current_month_total": analysis.get("total_spent", 0),
    }


async def ensure_demo_data() -> dict:
    """Keep demo data useful across months instead of leaving stale records forever."""
    transactions = get_collection("transactions")
    existing = await transactions.count_documents({"user_id": DEMO_USER_ID})
    if existing:
        analysis = await get_spending_analysis(DEMO_USER_ID, "current_month")
        if int(analysis.get("transaction_count", 0) or 0) > 0:
            return {
                "user_id": DEMO_USER_ID,
                "refreshed": False,
                "existing": existing,
                "current_month_transactions": analysis.get("transaction_count", 0),
                "current_month_total": analysis.get("total_spent", 0),
            }

    result = await refresh_demo_data()
    result["refreshed"] = True
    return result
