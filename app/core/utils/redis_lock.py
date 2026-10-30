from typing import Optional
import redis

from app.core.config import settings
from app.core.logger import logger


class REDIS_IDEMPOTENCY_LOCK:
    """
    Distributed Redis idempotency lock preventing duplicate concurrent execution.
    """

    def __init__(
        self
        , key_prefix  : str           = "idempotency_lock"
        , lock_ttl    : int           = 60
        , success_ttl : int           = 86400
        , redis_url   : Optional[str] = None
    ) -> None:
        self.key_prefix  = key_prefix
        self.lock_ttl    = lock_ttl
        self.success_ttl = success_ttl
        self.redis_url   = redis_url or settings.REDIS_URL
        self._client     : Optional[redis.Redis] = None

    def _get_client(self) -> Optional[redis.Redis]:
        if self._client is None:
            try:
                self._client = redis.Redis.from_url(self.redis_url, decode_responses=True)
            except Exception as exc:
                logger.warning(f"[REDIS_IDEMPOTENCY_LOCK] Redis init failed (fail-open): {str(exc)}")
                return None
        return self._client

    def _build_key(self, identifier: str) -> str:
        return f"{self.key_prefix}:{identifier}"

    def acquire(self, identifier: str) -> bool:
        """
        Attempt to acquire the lock for `identifier`.
        Returns True if acquired (or if Redis is unreachable -> fail-open),
        False if already locked or completed.
        """
        client = self._get_client()
        if client is None:
            return True
        key = self._build_key(identifier)
        try:
            acquired = client.set(key, "PROCESSING", nx=True, ex=self.lock_ttl)
            return bool(acquired)
        except Exception as exc:
            logger.warning(f"[REDIS_IDEMPOTENCY_LOCK] acquire failed for {key} (fail-open): {str(exc)}")
            return True

    def mark_success(self, identifier: str) -> bool:
        """
        Transition lock state to DONE with longer retention TTL.
        """
        client = self._get_client()
        if client is None:
            return False
        key = self._build_key(identifier)
        try:
            client.set(key, "DONE", ex=self.success_ttl)
            return True
        except Exception as exc:
            logger.warning(f"[REDIS_IDEMPOTENCY_LOCK] mark_success failed for {key}: {str(exc)}")
            return False

    def release(self, identifier: str) -> bool:
        """
        Delete the lock key so failed operations can be retried immediately.
        """
        client = self._get_client()
        if client is None:
            return False
        key = self._build_key(identifier)
        try:
            client.delete(key)
            return True
        except Exception as exc:
            logger.warning(f"[REDIS_IDEMPOTENCY_LOCK] release failed for {key}: {str(exc)}")
            return False

