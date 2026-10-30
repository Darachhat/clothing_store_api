from app.core.database import get_db as get_async_db, get_sync_db

# Template handlers (health, auth/clients, systems, telegram, logs) use synchronous SQLAlchemy Session via get_db
get_db = get_sync_db

__all__ = ["get_db", "get_sync_db", "get_async_db"]

