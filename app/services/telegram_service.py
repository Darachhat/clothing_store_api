import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import CONFLICT_EXCEPTION, NOT_FOUND_EXCEPTION
from app.core.utils.telegram_utils import TELEGRAM_UTILS
from app.models import TELEGRAM_BOT_MODEL, TELEGRAM_CHAT_MODEL
from app.schemas.base_schema import STATS_SUMMARY_SCHEMA
from app.schemas.telegram_schema import (
    TELEGRAM_BOT_CREATE_SCHEMA
    , TELEGRAM_BOT_LIST_OUT_SCHEMA
    , TELEGRAM_BOT_RESPONSE_SCHEMA
    , TELEGRAM_BOT_UPDATE_SCHEMA
    , TELEGRAM_CHAT_CREATE_SCHEMA
    , TELEGRAM_CHAT_LIST_OUT_SCHEMA
    , TELEGRAM_CHAT_RESPONSE_SCHEMA
    , TELEGRAM_CHAT_UPDATE_SCHEMA
)


def _parse_uuid(raw_id: str, label: str = "Resource") -> uuid.UUID:
    if isinstance(raw_id, uuid.UUID):
        return raw_id
    try:
        return uuid.UUID(str(raw_id))
    except (ValueError, TypeError):
        raise NOT_FOUND_EXCEPTION(f"{label} '{raw_id}' was not found.")


class TELEGRAM_BOT_SERVICE:
    """
    CRUD service for auth.telegram_bot (TELEGRAM_BOT_MODEL).
    """

    @staticmethod
    def _to_schema(row: TELEGRAM_BOT_MODEL) -> TELEGRAM_BOT_RESPONSE_SCHEMA:
        return TELEGRAM_BOT_RESPONSE_SCHEMA(
            id                 = str(row.id)
            , code             = row.code or ""
            , name             = row.name or ""
            , user_id          = row.user_id
            , username         = row.username
            , token            = row.token
            , description      = row.description
            , status_code      = row.status_code or "active"
            , created_datetime = row.created_datetime
            , updated_datetime = row.updated_datetime
        )

    @staticmethod
    def list_bots(
        db            : Session
        , search      : Optional[str] = None
        , status_code : Optional[str] = None
        , page        : int           = 1
        , size        : int           = 50
        , sort_by     : str           = "name"
        , sort_order  : str           = "asc"
    ) -> TELEGRAM_BOT_LIST_OUT_SCHEMA:
        base_query = db.query(TELEGRAM_BOT_MODEL).filter(
            TELEGRAM_BOT_MODEL.deleted_datetime.is_(None)
        )
        total_all  = base_query.count()
        active_cnt = base_query.filter(
            TELEGRAM_BOT_MODEL.status_code.in_(["active", "ACTIVE"])
        ).count()

        query = base_query
        if search:
            like  = f"%{search}%"
            query = query.filter(
                TELEGRAM_BOT_MODEL.code.ilike(like)
                | TELEGRAM_BOT_MODEL.name.ilike(like)
                | TELEGRAM_BOT_MODEL.username.ilike(like)
                | TELEGRAM_BOT_MODEL.description.ilike(like)
            )
        if status_code:
            query = query.filter(TELEGRAM_BOT_MODEL.status_code == status_code)

        col_map = {
            "code"               : TELEGRAM_BOT_MODEL.code
            , "name"             : TELEGRAM_BOT_MODEL.name
            , "username"         : TELEGRAM_BOT_MODEL.username
            , "status_code"      : TELEGRAM_BOT_MODEL.status_code
            , "created_datetime" : TELEGRAM_BOT_MODEL.created_datetime
        }
        sort_col = col_map.get(sort_by, TELEGRAM_BOT_MODEL.name)
        query    = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())

        total = query.count()
        rows  = query.offset((page - 1) * size).limit(size).all()

        return TELEGRAM_BOT_LIST_OUT_SCHEMA(
            items   = [TELEGRAM_BOT_SERVICE._to_schema(r) for r in rows]
            , total = total
            , page  = page
            , size  = size
            , stats = STATS_SUMMARY_SCHEMA(
                total      = total_all
                , active   = active_cnt
                , inactive = max(0, total_all - active_cnt)
            )
        )

    @staticmethod
    def get_bot(
        db       : Session
        , bot_id : str
    ) -> TELEGRAM_BOT_RESPONSE_SCHEMA:
        bot_uuid = _parse_uuid(bot_id, "Telegram bot")
        row = (
            db.query(TELEGRAM_BOT_MODEL)
            .filter(
                TELEGRAM_BOT_MODEL.id == bot_uuid
                , TELEGRAM_BOT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not row:
            raise NOT_FOUND_EXCEPTION(f"Telegram bot '{bot_id}' was not found.")
        return TELEGRAM_BOT_SERVICE._to_schema(row)

    @staticmethod
    def create_bot(
        db     : Session
        , data : TELEGRAM_BOT_CREATE_SCHEMA
    ) -> TELEGRAM_BOT_RESPONSE_SCHEMA:
        existing = (
            db.query(TELEGRAM_BOT_MODEL)
            .filter(
                TELEGRAM_BOT_MODEL.code == data.code
                , TELEGRAM_BOT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if existing:
            raise CONFLICT_EXCEPTION(f"Telegram bot code '{data.code}' already exists.")

        row = TELEGRAM_BOT_MODEL(
            code          = data.code
            , name        = data.name
            , user_id     = data.user_id
            , username    = data.username
            , token       = data.token
            , description = data.description
            , status_code = data.status_code
            , created_by  = "admin"
            , updated_by  = "admin"
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return TELEGRAM_BOT_SERVICE._to_schema(row)

    @staticmethod
    def update_bot(
        db       : Session
        , bot_id : str
        , data   : TELEGRAM_BOT_UPDATE_SCHEMA
    ) -> TELEGRAM_BOT_RESPONSE_SCHEMA:
        bot_uuid = _parse_uuid(bot_id, "Telegram bot")
        row = (
            db.query(TELEGRAM_BOT_MODEL)
            .filter(
                TELEGRAM_BOT_MODEL.id == bot_uuid
                , TELEGRAM_BOT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not row:
            raise NOT_FOUND_EXCEPTION(f"Telegram bot '{bot_id}' was not found.")

        updates  = data.model_dump(exclude_unset=True)
        new_code = updates.get("code")
        if new_code and new_code != row.code:
            conflict = (
                db.query(TELEGRAM_BOT_MODEL)
                .filter(
                    TELEGRAM_BOT_MODEL.code == new_code
                    , TELEGRAM_BOT_MODEL.id != row.id
                    , TELEGRAM_BOT_MODEL.deleted_datetime.is_(None)
                )
                .first()
            )
            if conflict:
                raise CONFLICT_EXCEPTION(f"Telegram bot code '{new_code}' already exists.")

        for field, value in updates.items():
            if value is not None:
                setattr(row, field, value)

        row.updated_datetime = datetime.now(timezone.utc)
        row.updated_by       = "admin"
        db.commit()
        db.refresh(row)
        return TELEGRAM_BOT_SERVICE._to_schema(row)

    @staticmethod
    def delete_bot(
        db       : Session
        , bot_id : str
    ) -> None:
        bot_uuid = _parse_uuid(bot_id, "Telegram bot")
        row = (
            db.query(TELEGRAM_BOT_MODEL)
            .filter(
                TELEGRAM_BOT_MODEL.id == bot_uuid
                , TELEGRAM_BOT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not row:
            raise NOT_FOUND_EXCEPTION(f"Telegram bot '{bot_id}' was not found.")

        row.deleted_datetime = datetime.now(timezone.utc)
        row.deleted_by       = "admin"
        row.status_code      = "deleted"
        db.commit()


class TELEGRAM_CHAT_SERVICE:
    """
    CRUD service for auth.telegram_chat (TELEGRAM_CHAT_MODEL).
    """

    @staticmethod
    def _to_schema(row: TELEGRAM_CHAT_MODEL) -> TELEGRAM_CHAT_RESPONSE_SCHEMA:
        return TELEGRAM_CHAT_RESPONSE_SCHEMA(
            id                  = str(row.id)
            , code              = row.code or ""
            , telegram_bot_code = row.telegram_bot_code or ""
            , name              = row.name or ""
            , chat_type         = row.chat_type
            , link              = row.link
            , chat_id           = row.chat_id
            , thread_id         = row.thread_id
            , description       = row.description
            , status_code       = row.status_code or "active"
            , created_datetime  = row.created_datetime
            , updated_datetime  = row.updated_datetime
        )

    @staticmethod
    def list_chats(
        db                  : Session
        , search            : Optional[str] = None
        , telegram_bot_code : Optional[str] = None
        , chat_type         : Optional[str] = None
        , status_code       : Optional[str] = None
        , page              : int           = 1
        , size              : int           = 50
        , sort_by           : str           = "name"
        , sort_order        : str           = "asc"
    ) -> TELEGRAM_CHAT_LIST_OUT_SCHEMA:
        base_query = db.query(TELEGRAM_CHAT_MODEL).filter(
            TELEGRAM_CHAT_MODEL.deleted_datetime.is_(None)
        )
        total_all  = base_query.count()
        active_cnt = base_query.filter(
            TELEGRAM_CHAT_MODEL.status_code.in_(["active", "ACTIVE"])
        ).count()

        query = base_query
        if search:
            like  = f"%{search}%"
            query = query.filter(
                TELEGRAM_CHAT_MODEL.code.ilike(like)
                | TELEGRAM_CHAT_MODEL.name.ilike(like)
                | TELEGRAM_CHAT_MODEL.chat_id.ilike(like)
                | TELEGRAM_CHAT_MODEL.description.ilike(like)
            )
        if telegram_bot_code:
            query = query.filter(TELEGRAM_CHAT_MODEL.telegram_bot_code == telegram_bot_code)
        if chat_type:
            query = query.filter(TELEGRAM_CHAT_MODEL.chat_type == chat_type)
        if status_code:
            query = query.filter(TELEGRAM_CHAT_MODEL.status_code == status_code)

        col_map = {
            "code"                : TELEGRAM_CHAT_MODEL.code
            , "name"              : TELEGRAM_CHAT_MODEL.name
            , "telegram_bot_code" : TELEGRAM_CHAT_MODEL.telegram_bot_code
            , "chat_type"         : TELEGRAM_CHAT_MODEL.chat_type
            , "status_code"       : TELEGRAM_CHAT_MODEL.status_code
            , "created_datetime"  : TELEGRAM_CHAT_MODEL.created_datetime
        }
        sort_col = col_map.get(sort_by, TELEGRAM_CHAT_MODEL.name)
        query    = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())

        total = query.count()
        rows  = query.offset((page - 1) * size).limit(size).all()

        return TELEGRAM_CHAT_LIST_OUT_SCHEMA(
            items   = [TELEGRAM_CHAT_SERVICE._to_schema(r) for r in rows]
            , total = total
            , page  = page
            , size  = size
            , stats = STATS_SUMMARY_SCHEMA(
                total      = total_all
                , active   = active_cnt
                , inactive = max(0, total_all - active_cnt)
            )
        )

    @staticmethod
    def get_chat(
        db        : Session
        , chat_id : str
    ) -> TELEGRAM_CHAT_RESPONSE_SCHEMA:
        chat_uuid = _parse_uuid(chat_id, "Telegram chat")
        row = (
            db.query(TELEGRAM_CHAT_MODEL)
            .filter(
                TELEGRAM_CHAT_MODEL.id == chat_uuid
                , TELEGRAM_CHAT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not row:
            raise NOT_FOUND_EXCEPTION(f"Telegram chat '{chat_id}' was not found.")
        return TELEGRAM_CHAT_SERVICE._to_schema(row)

    @staticmethod
    def create_chat(
        db     : Session
        , data : TELEGRAM_CHAT_CREATE_SCHEMA
    ) -> TELEGRAM_CHAT_RESPONSE_SCHEMA:
        existing = (
            db.query(TELEGRAM_CHAT_MODEL)
            .filter(
                TELEGRAM_CHAT_MODEL.code == data.code
                , TELEGRAM_CHAT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if existing:
            raise CONFLICT_EXCEPTION(f"Telegram chat code '{data.code}' already exists.")

        row = TELEGRAM_CHAT_MODEL(
            code                = data.code
            , telegram_bot_code = data.telegram_bot_code
            , name              = data.name
            , chat_type         = data.chat_type
            , link              = data.link
            , chat_id           = data.chat_id
            , thread_id         = data.thread_id
            , description       = data.description
            , status_code       = data.status_code
            , created_by        = "admin"
            , updated_by        = "admin"
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return TELEGRAM_CHAT_SERVICE._to_schema(row)

    @staticmethod
    def update_chat(
        db        : Session
        , chat_id : str
        , data    : TELEGRAM_CHAT_UPDATE_SCHEMA
    ) -> TELEGRAM_CHAT_RESPONSE_SCHEMA:
        chat_uuid = _parse_uuid(chat_id, "Telegram chat")
        row = (
            db.query(TELEGRAM_CHAT_MODEL)
            .filter(
                TELEGRAM_CHAT_MODEL.id == chat_uuid
                , TELEGRAM_CHAT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not row:
            raise NOT_FOUND_EXCEPTION(f"Telegram chat '{chat_id}' was not found.")

        updates  = data.model_dump(exclude_unset=True)
        new_code = updates.get("code")
        if new_code and new_code != row.code:
            conflict = (
                db.query(TELEGRAM_CHAT_MODEL)
                .filter(
                    TELEGRAM_CHAT_MODEL.code == new_code
                    , TELEGRAM_CHAT_MODEL.id != row.id
                    , TELEGRAM_CHAT_MODEL.deleted_datetime.is_(None)
                )
                .first()
            )
            if conflict:
                raise CONFLICT_EXCEPTION(f"Telegram chat code '{new_code}' already exists.")

        for field, value in updates.items():
            if value is not None:
                setattr(row, field, value)

        row.updated_datetime = datetime.now(timezone.utc)
        row.updated_by       = "admin"
        db.commit()
        db.refresh(row)
        return TELEGRAM_CHAT_SERVICE._to_schema(row)

    @staticmethod
    def delete_chat(
        db        : Session
        , chat_id : str
    ) -> None:
        chat_uuid = _parse_uuid(chat_id, "Telegram chat")
        row = (
            db.query(TELEGRAM_CHAT_MODEL)
            .filter(
                TELEGRAM_CHAT_MODEL.id == chat_uuid
                , TELEGRAM_CHAT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not row:
            raise NOT_FOUND_EXCEPTION(f"Telegram chat '{chat_id}' was not found.")

        row.deleted_datetime = datetime.now(timezone.utc)
        row.deleted_by       = "admin"
        row.status_code      = "deleted"
        db.commit()


class TELEGRAM_SERVICE:
    """
    High-level Telegram notification service for operational alerts, log rotation summaries,
    and outbound message dispatch.
    """

    @staticmethod
    async def send_notification(
        chat_code    : str
        , text       : str
        , parse_mode : str               = "HTML"
        , session    : Optional[Session] = None
    ) -> Dict[str, Any]:
        return await TELEGRAM_UTILS.send_to_chat(
            chat_code    = chat_code
            , text       = text
            , parse_mode = parse_mode
            , session    = session
        )

    @staticmethod
    async def send_log_rotation_report(
        rotation_summary : Dict[str, Any]
        , chat_code      : Optional[str]     = None
        , session        : Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        target_chat = chat_code or settings.TELEGRAM_ALERT_CHAT_CODE
        if not target_chat:
            return None

        text = (
            f"<b>[{settings.COMPONENT_NAME}] Daily Log Rotation Completed</b>\n"
            f"• Date: <code>{rotation_summary.get('date')}</code>\n"
            f"• Archived Files: <code>{len(rotation_summary.get('archived_files', []))}</code>\n"
            f"• Archived Lines: <code>{rotation_summary.get('archived_lines', 0)}</code>\n"
            f"• Purged Old Archives: <code>{len(rotation_summary.get('deleted_archives', []))}</code>"
        )
        return await TELEGRAM_UTILS.send_to_chat(
            chat_code = target_chat
            , text    = text
            , session = session
        )

