"""Notification background tasks — Telegram integration."""
from __future__ import annotations

import httpx
from loguru import logger

from app.core.config import settings
from app.tasks.celery_app import celery_app


def _send_tg(message: str) -> bool:
    """Synchronously POST a message to the Telegram Bot API.

    Returns True on success, False on failure.
    Handles supergroup migration (migrate_to_chat_id).
    """
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_GROUP_ID

    if not token or not chat_id:
        logger.debug("[TG] Bot token or group ID not configured — skipping")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json=payload)
            data = resp.json()

        if not data.get("ok"):
            # Handle supergroup migration
            if data.get("error_code") == 400 and "migrate_to_chat_id" in str(data):
                new_id = data.get("parameters", {}).get("migrate_to_chat_id")
                if new_id:
                    logger.warning(f"[TG] Group migrated to supergroup {new_id} — retrying")
                    payload["chat_id"] = new_id
                    with httpx.Client(timeout=10) as c2:
                        resp2 = c2.post(url, json=payload)
                        data2 = resp2.json()
                    return bool(data2.get("ok"))

            logger.warning(f"[TG] sendMessage failed: {data}")
            return False

        return True

    except Exception as exc:
        logger.error(f"[TG] sendMessage exception: {exc}")
        return False


@celery_app.task(name="app.tasks.notification_tasks.send_telegram", bind=True, max_retries=3)
def send_telegram(self, message: str) -> dict:
    """Send a Markdown message to the configured Telegram group.

    Retries up to 3 times with exponential back-off on failure.
    """
    ok = _send_tg(message)
    if not ok:
        try:
            raise self.retry(countdown=2 ** self.request.retries)
        except self.MaxRetriesExceededError:
            logger.error(f"[TG] Max retries exceeded for message: {message[:80]}")
    return {"ok": ok, "message": message[:80]}


@celery_app.task(name="app.tasks.notification_tasks.send_notification")
def send_notification(message: str, channel: str = "log") -> dict:
    """Legacy compatibility shim — routes to Telegram."""
    logger.info(f"[NOTIFICATION/{channel.upper()}] {message}")
    if channel.lower() == "telegram":
        _send_tg(message)
    return {"status": "sent", "channel": channel, "message": message}
