import socket
import ssl
from contextlib import asynccontextmanager
from pymongo import AsyncMongoClient, ASCENDING, DESCENDING
from app.config import settings

client = AsyncMongoClient(
    settings.mongodb_uri,
    serverSelectionTimeoutMS=5000,
    tz_aware=True
)
db = client[settings.mongodb_database]


async def init_db():
    host = "ac-612hpz7-shard-00-00.woywloq.mongodb.net"

    print("=== RENDER NETWORK DIAGNOSTIC START ===", flush=True)

    try:
        addresses = socket.getaddrinfo(host, 27017)
        print("DNS SUCCESS:", addresses, flush=True)
    except Exception as exc:
        print("DNS FAILED:", repr(exc), flush=True)

    try:
        raw_socket = socket.create_connection((host, 27017), timeout=10)
        print("TCP CONNECTION SUCCESS", flush=True)

        context = ssl.create_default_context()
        with context.wrap_socket(raw_socket, server_hostname=host) as tls:
            print("TLS SUCCESS:", tls.version(), flush=True)
            print("TLS CIPHER:", tls.cipher(), flush=True)

    except Exception as exc:
        print("TCP/TLS FAILED:", repr(exc), flush=True)

    print("=== RENDER NETWORK DIAGNOSTIC END ===", flush=True)

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
