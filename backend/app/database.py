from contextlib import asynccontextmanager
from pymongo import AsyncMongoClient, ASCENDING, DESCENDING
from app.config import settings

client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000, tz_aware=True)
db = client[settings.mongodb_database]

async def init_db():
    await client.admin.command("ping")
    await db.users.create_index([("email", ASCENDING)], unique=True)
    await db.tasks.create_index([("assigned_to", ASCENDING), ("created_at", DESCENDING)])
    await db.tasks.create_index([("deadline", ASCENDING), ("status", ASCENDING)])
    await db.task_events.create_index([("task_id", ASCENDING), ("created_at", DESCENDING)])
    await db.notifications.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db.notifications.create_index([("dedupe_key", ASCENDING)], unique=True, sparse=True)
    await db.predictions.create_index([("task_id", ASCENDING), ("created_at", DESCENDING)])

async def close_db():
    await client.close()
