"""Notification background tasks — Telegram integration."""
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
from loguru import logger

from app.core.config import settings
from app.core.database import get_static_session
from app.core.utils.telegram_utils import TELEGRAM_UTILS
from app.tasks.celery_app import celery_app


# ── Internal helpers ───────────────────────────────────────────────────────────

def _send_tg_via_db(message: str, chat_code: str) -> bool:
    """Send *message* via the DB-backed TELEGRAM_UTILS path.

    Resolves the bot token and chat_id from the database, calls the Telegram
    Bot API synchronously, persists an outbound record, and handles supergroup
    migration.  Returns True on success, False on any failure.
    """
    session = get_static_session()
    try:
        dest = TELEGRAM_UTILS.resolve_destination(chat_code=chat_code, session=session)
        if not dest:
            logger.warning(
                f"[TG] resolve_destination returned None for chat_code={chat_code!r} — skipping"
            )
            TELEGRAM_UTILS._write_outbound(
                session              = session,
                telegram_chat_code   = chat_code,
                chat_type            = None,
                telegram_bot_code    = None,
                chat_id              = None,
                thread_id            = None,
                request_object       = {"chat_code": chat_code, "text": message},
                response_object      = None,
                is_success           = False,
                error_code           = 404,
                error_detail         = f"Telegram destination '{chat_code}' not found or inactive.",
            )
            return False

        url: str = f"https://api.telegram.org/bot{dest.bot_token}/sendMessage"
        payload: Dict[str, Any] = {
            "chat_id"                 : dest.chat_id,
            "text"                    : message,
            "parse_mode"              : "Markdown",
            "disable_web_page_preview": True,
        }
        if dest.thread_id:
            try:
                payload["message_thread_id"] = int(dest.thread_id)
            except ValueError:
                payload["message_thread_id"] = dest.thread_id

        req_obj = {
            "chat_id"   : dest.chat_id,
            "thread_id" : dest.thread_id,
            "parse_mode": "Markdown",
            "text"      : message,
        }

        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, json=payload)
                data: Dict[str, Any] = resp.json()

            if not data.get("ok"):
                # Handle supergroup migration
                if data.get("error_code") == 400 and "migrate_to_chat_id" in str(data):
                    new_id = data.get("parameters", {}).get("migrate_to_chat_id")
                    if new_id:
                        logger.warning(f"[TG] Group migrated to supergroup {new_id} — retrying")
                        payload["chat_id"] = str(new_id)
                        with httpx.Client(timeout=10) as c2:
                            resp2 = c2.post(url, json=payload)
                            data = resp2.json()

        except Exception as exc:
            logger.error(f"[TG] sendMessage exception: {exc}")
            data = {"ok": False, "error_code": 500, "description": str(exc)}

        is_ok   = bool(data.get("ok"))
        msg_obj = data.get("result") or {}
        msg_id  = msg_obj.get("message_id") if isinstance(msg_obj, dict) else None
        err_cd  = data.get("error_code") if not is_ok else None
        err_dtl = data.get("description") if not is_ok else None

        if not is_ok:
            logger.warning(f"[TG] sendMessage failed: {data}")

        TELEGRAM_UTILS._write_outbound(
            session              = session,
            telegram_chat_code   = dest.chat_code,
            chat_type            = dest.chat_type,
            telegram_bot_code    = dest.bot_code,
            chat_id              = dest.chat_id,
            thread_id            = dest.thread_id,
            request_object       = req_obj,
            response_object      = data,
            is_success           = is_ok,
            telegram_message_id  = str(msg_id) if msg_id is not None else None,
            error_code           = err_cd,
            error_detail         = err_dtl,
        )
        return is_ok

    finally:
        session.close()


def _send_tg(message: str) -> bool:
    """Route Telegram delivery strictly through the DB-backed path (auth.telegram_chat).

    Resolves bot token and chat destination from the database using TELEGRAM_ALERT_CHAT_CODE
    (defaulting to 'clothing_store_alerts').
    """
    chat_code: str = settings.TELEGRAM_ALERT_CHAT_CODE or "clothing_store_alerts"
    return _send_tg_via_db(message=message, chat_code=chat_code)


# ── Celery tasks ───────────────────────────────────────────────────────────────

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
