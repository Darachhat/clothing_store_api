import json
from typing import Any, Callable, Dict, List, Optional
import redis

from app.core.config import settings
from app.core.logger import logger


class REDIS_STREAM_SUBSCRIBER:
    """
    Redis Streams consumer group subscriber with dead-letter queue (DLQ) and stream trimming.
    """

    def __init__(
        self
        , stream_name        : str
        , group_name         : str
        , consumer_name      : str
        , max_delivery_count : int           = 5
        , max_stream_length  : int           = 10000
        , redis_url          : Optional[str] = None
    ) -> None:
        self.stream_name        = stream_name
        self.dlq_stream_name    = f"{stream_name}:dlq"
        self.group_name         = group_name
        self.consumer_name      = consumer_name
        self.max_delivery_count = max_delivery_count
        self.max_stream_length  = max_stream_length
        self.redis_url          = redis_url or settings.REDIS_URL
        self._client            : Optional[redis.Redis] = None

    def get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    def ensure_group(self) -> None:
        client = self.get_client()
        try:
            client.xgroup_create(
                name        = self.stream_name
                , groupname = self.group_name
                , id        = "0"
                , mkstream  = True
            )
        except redis.exceptions.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def publish(self, payload: Dict[str, Any]) -> str:
        """
        Publish a dictionary event to the Redis stream and trim stream to max_stream_length.
        """
        client = self.get_client()
        serialized = {
            k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v))
            for k, v in payload.items()
        }
        msg_id = client.xadd(
            self.stream_name
            , serialized
            , maxlen      = self.max_stream_length
            , approximate = True
        )
        return str(msg_id)

    def process_batch(
        self
        , handler  : Callable[[str, Dict[str, Any]], None]
        , count    : int = 10
        , block_ms : int = 1000
    ) -> int:
        """
        Read up to `count` new messages from the consumer group, invoke `handler(msg_id, data)`,
        and XACK on success. Moves poison messages exceeding max_delivery_count to DLQ.
        """
        client = self.get_client()
        self.ensure_group()

        entries = client.xreadgroup(
            groupname      = self.group_name
            , consumername = self.consumer_name
            , streams      = {self.stream_name: ">"}
            , count        = count
            , block        = block_ms
        )
        if not entries:
            return 0

        processed = 0
        for _, messages in entries:
            for msg_id, fields in messages:
                try:
                    handler(msg_id, fields)
                    client.xack(self.stream_name, self.group_name, msg_id)
                    processed += 1
                except Exception as exc:
                    logger.error(
                        f"[REDIS_STREAM_SUBSCRIBER] Error processing {msg_id} on {self.stream_name}: {str(exc)}"
                    )
                    self._handle_failure(msg_id=msg_id, fields=fields, error=str(exc))
        return processed

    def _handle_failure(
        self
        , msg_id : str
        , fields : Dict[str, Any]
        , error  : str
    ) -> None:
        client = self.get_client()
        try:
            pending_info : List[Dict[str, Any]] = client.xpending_range(
                name        = self.stream_name
                , groupname = self.group_name
                , min       = msg_id
                , max       = msg_id
                , count     = 1
            )
            times_delivered = 1
            if pending_info:
                times_delivered = int(pending_info[0].get("times_delivered", 1))

            if times_delivered >= self.max_delivery_count:
                dlq_payload = dict(fields)
                dlq_payload["_original_msg_id"] = msg_id
                dlq_payload["_error"]           = error
                client.xadd(self.dlq_stream_name, dlq_payload)
                client.xack(self.stream_name, self.group_name, msg_id)
                logger.warning(
                    f"[REDIS_STREAM_SUBSCRIBER] Moved poison message {msg_id} to DLQ {self.dlq_stream_name}"
                )
        except Exception as exc:
            logger.error(f"[REDIS_STREAM_SUBSCRIBER] DLQ handling failed for {msg_id}: {str(exc)}")

