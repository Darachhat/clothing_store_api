from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.constants import HTTP_TIMEOUT_SECONDS, TELEGRAM_API_BASE_URL
from app.core.database import get_static_session
from app.core.logger import logger
from app.core.utils.http_client import HTTP_CLIENT
from app.models import TELEGRAM_BOT_MODEL, TELEGRAM_CHAT_MODEL
from app.models import TELEGRAM_OUTBOUND_MODEL


@dataclass
class TELEGRAM_DESTINATION:
    chat_code : str
    chat_type : Optional[str]
    bot_code  : str
    bot_token : str
    chat_id   : str
    thread_id : Optional[str] = None


class TELEGRAM_UTILS:
    """
    Utility class for resolving Telegram bot/chat destinations from the database,
    sending messages or documents via the Telegram Bot API, and persisting
    outbound delivery records to track.telegram_outbound.
    """

    @staticmethod
    def get_bot(
        bot_code   : str
        , session  : Optional[Session] = None
    ) -> Optional[TELEGRAM_BOT_MODEL]:
        own_session = session is None
        db          = session or get_static_session()
        try:
            return (
                db.query(TELEGRAM_BOT_MODEL)
                .filter(
                    TELEGRAM_BOT_MODEL.code == bot_code
                    , TELEGRAM_BOT_MODEL.deleted_datetime.is_(None)
                    , TELEGRAM_BOT_MODEL.status_code.in_(["active", "ACTIVE"])
                )
                .first()
            )
        finally:
            if own_session:
                db.close()

    @staticmethod
    def get_chat(
        chat_code  : str
        , session  : Optional[Session] = None
    ) -> Optional[TELEGRAM_CHAT_MODEL]:
        own_session = session is None
        db          = session or get_static_session()
        try:
            return (
                db.query(TELEGRAM_CHAT_MODEL)
                .filter(
                    TELEGRAM_CHAT_MODEL.code == chat_code
                    , TELEGRAM_CHAT_MODEL.deleted_datetime.is_(None)
                    , TELEGRAM_CHAT_MODEL.status_code.in_(["active", "ACTIVE"])
                )
                .first()
            )
        finally:
            if own_session:
                db.close()

    @staticmethod
    def resolve_destination(
        chat_code  : str
        , session  : Optional[Session] = None
    ) -> Optional[TELEGRAM_DESTINATION]:
        own_session = session is None
        db          = session or get_static_session()
        try:
            chat = TELEGRAM_UTILS.get_chat(chat_code=chat_code, session=db)
            if not chat or not chat.chat_id:
                logger.warning(f"[TELEGRAM_UTILS] Chat not found or missing chat_id: code={chat_code}")
                return None

            bot = TELEGRAM_UTILS.get_bot(bot_code=chat.telegram_bot_code, session=db)
            if not bot or not bot.token:
                logger.warning(f"[TELEGRAM_UTILS] Bot not found or missing token: code={chat.telegram_bot_code}")
                return None

            return TELEGRAM_DESTINATION(
                chat_code   = chat.code
                , chat_type = chat.chat_type
                , bot_code  = bot.code
                , bot_token = bot.token
                , chat_id   = str(chat.chat_id)
                , thread_id = str(chat.thread_id) if chat.thread_id else None
            )
        finally:
            if own_session:
                db.close()

    @staticmethod
    def _write_outbound(
        session               : Optional[Session]
        , telegram_chat_code  : Optional[str]
        , chat_type           : Optional[str]
        , telegram_bot_code   : Optional[str]
        , chat_id             : Optional[str]
        , thread_id           : Optional[str]
        , request_object      : Optional[Dict[str, Any]]
        , response_object     : Optional[Dict[str, Any]]
        , is_success          : bool
        , telegram_message_id : Optional[str] = None
        , error_code          : Optional[int] = None
        , error_detail        : Optional[str] = None
    ) -> Optional[TELEGRAM_OUTBOUND_MODEL]:
        own_session = session is None
        db          = session or get_static_session()
        try:
            row = TELEGRAM_OUTBOUND_MODEL(
                telegram_chat_code    = telegram_chat_code
                , chat_type           = chat_type
                , telegram_bot_code   = telegram_bot_code
                , chat_id             = str(chat_id) if chat_id is not None else None
                , thread_id           = str(thread_id) if thread_id is not None else None
                , request_object      = request_object
                , response_object     = response_object
                , is_success          = is_success
                , telegram_message_id = str(telegram_message_id) if telegram_message_id is not None else None
                , error_code          = error_code
                , error_detail        = error_detail
                , status_code         = "active"
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row
        except Exception as exc:
            logger.error(f"[TELEGRAM_UTILS] Failed to write telegram_outbound record: {str(exc)}")
            db.rollback()
            return None
        finally:
            if own_session:
                db.close()

    @staticmethod
    async def send_message(
        bot_token     : str
        , chat_id     : str
        , text        : str
        , parse_mode  : str           = "HTML"
        , thread_id   : Optional[str] = None
        , timeout     : int           = HTTP_TIMEOUT_SECONDS
    ) -> Dict[str, Any]:
        """
        Send a text message to a Telegram chat/topic via the Telegram Bot API.
        Automatically retries without message_thread_id if the topic thread was deleted.
        """
        url = f"{TELEGRAM_API_BASE_URL}/bot{bot_token}/sendMessage"
        payload : Dict[str, Any] = {
            "chat_id"                    : chat_id
            , "text"                     : text
            , "parse_mode"               : parse_mode
            , "disable_web_page_preview" : True
        }
        if thread_id:
            try:
                payload["message_thread_id"] = int(thread_id)
            except ValueError:
                payload["message_thread_id"] = thread_id

        try:
            res = await HTTP_CLIENT.request(
                method             = "POST"
                , url              = url
                , json_data        = payload
                , timeout          = timeout
                , system_code      = "telegram_api"
                , raise_for_status = False
            )
            if not res.get("ok") and thread_id and "thread" in str(res.get("description", "")).lower():
                payload.pop("message_thread_id", None)
                res = await HTTP_CLIENT.request(
                    method             = "POST"
                    , url              = url
                    , json_data        = payload
                    , timeout          = timeout
                    , system_code      = "telegram_api"
                    , raise_for_status = False
                )
            return res
        except Exception as exc:
            logger.error(f"[TELEGRAM_UTILS] send_message error: {str(exc)}")
            return {"ok": False, "error_code": 500, "description": str(exc)}

    @staticmethod
    async def send_to_chat(
        chat_code    : str
        , text       : str
        , parse_mode : str               = "HTML"
        , session    : Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        High-level helper: resolve chat_code -> send message -> persist track.telegram_outbound.
        """
        dest = TELEGRAM_UTILS.resolve_destination(chat_code=chat_code, session=session)
        if not dest:
            TELEGRAM_UTILS._write_outbound(
                session               = session
                , telegram_chat_code  = chat_code
                , chat_type           = None
                , telegram_bot_code   = None
                , chat_id             = None
                , thread_id           = None
                , request_object      = {"chat_code": chat_code, "text": text}
                , response_object     = None
                , is_success          = False
                , error_code          = 404
                , error_detail        = f"Telegram destination '{chat_code}' not found or inactive."
            )
            return {"ok": False, "error_code": 404, "description": f"Destination '{chat_code}' not found."}

        req_obj = {
            "chat_id"      : dest.chat_id
            , "thread_id"  : dest.thread_id
            , "parse_mode" : parse_mode
            , "text"       : text
        }
        res = await TELEGRAM_UTILS.send_message(
            bot_token    = dest.bot_token
            , chat_id    = dest.chat_id
            , text       = text
            , parse_mode = parse_mode
            , thread_id  = dest.thread_id
        )

        is_ok   = bool(res.get("ok"))
        msg_obj = res.get("result") or {}
        msg_id  = msg_obj.get("message_id") if isinstance(msg_obj, dict) else None
        err_cd  = res.get("error_code") if not is_ok else None
        err_dtl = res.get("description") if not is_ok else None

        TELEGRAM_UTILS._write_outbound(
            session               = session
            , telegram_chat_code  = dest.chat_code
            , chat_type           = dest.chat_type
            , telegram_bot_code   = dest.bot_code
            , chat_id             = dest.chat_id
            , thread_id           = dest.thread_id
            , request_object      = req_obj
            , response_object     = res
            , is_success          = is_ok
            , telegram_message_id = str(msg_id) if msg_id is not None else None
            , error_code          = err_cd
            , error_detail        = err_dtl
        )
        return res

