import os
from typing import Optional

from dotenv import load_dotenv
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        uri = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
        _client = AsyncIOMotorClient(
            uri,
            maxPoolSize=10,
            serverSelectionTimeoutMS=int(os.getenv("MONGODB_TIMEOUT_MS", "3000")),
        )
        logger.info("MongoDB client created")
    return _client


def get_db():
    return get_client()[os.getenv("DATABASE_NAME", "financial_assistant")]


def get_collection(name: str):
    return get_db()[name]


async def ping_database() -> bool:
    try:
        await get_client().admin.command("ping")
        return True
    except Exception as exc:
        logger.warning(f"MongoDB ping failed: {exc}")
        return False


async def create_indexes() -> None:
    db = get_db()
    await db.transactions.create_index([("user_id", 1), ("date", -1)])
    await db.transactions.create_index([("user_id", 1), ("category", 1)])
    await db.users.create_index("email", unique=True)
    await db.conversations.create_index([("user_id", 1), ("timestamp", -1)])
    await db.goals.create_index([("user_id", 1), ("created_at", -1)])
    logger.info("MongoDB indexes created")


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB client closed")
