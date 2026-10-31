import socket
import ssl
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

    print("=== TLS VERSION DIAGNOSTIC START ===", flush=True)
    print("OpenSSL:", ssl.OPENSSL_VERSION, flush=True)

    for version in [ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3]:
        try:
            context = ssl.create_default_context()
            context.minimum_version = version
            context.maximum_version = version

            with socket.create_connection(
                (host, 27017), timeout=10
            ) as raw:
                with context.wrap_socket(
                    raw, server_hostname=host
                ) as tls:
                    print(
                        f"{version.name} SUCCESS: {tls.version()}",
                        flush=True
                    )

        except Exception as exc:
            print(
                f"{version.name} FAILED: {repr(exc)}",
                flush=True
            )

    print("=== TLS VERSION DIAGNOSTIC END ===", flush=True)

    await client.admin.command("ping")

    await db.users.create_index(
        [("email", ASCENDING)], unique=True
    )
    await db.tasks.create_index(
        [("assigned_to", ASCENDING), ("created_at", DESCENDING)]
    )
    await db.tasks.create_index(
        [("deadline", ASCENDING), ("status", ASCENDING)]
    )
    await db.task_events.create_index(
        [("task_id", ASCENDING), ("created_at", DESCENDING)]
    )
    await db.notifications.create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)]
    )
    await db.notifications.create_index(
        [("dedupe_key", ASCENDING)], unique=True, sparse=True
    )
    await db.predictions.create_index(
        [("task_id", ASCENDING), ("created_at", DESCENDING)]
    )


async def close_db():
    await client.close()

    await client.close()
