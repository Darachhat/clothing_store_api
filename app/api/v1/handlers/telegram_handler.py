from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps.database import get_db
from app.schemas.base_schema import RESPONSE_ENVELOPE
from app.schemas.telegram_schema import (
    TELEGRAM_BOT_CREATE_SCHEMA
    , TELEGRAM_BOT_LIST_OUT_SCHEMA
    , TELEGRAM_BOT_RESPONSE_SCHEMA
    , TELEGRAM_BOT_UPDATE_SCHEMA
    , TELEGRAM_CHAT_CREATE_SCHEMA
    , TELEGRAM_CHAT_LIST_OUT_SCHEMA
    , TELEGRAM_CHAT_RESPONSE_SCHEMA
    , TELEGRAM_CHAT_UPDATE_SCHEMA
    , TELEGRAM_SEND_MESSAGE_SCHEMA
)
from app.services.telegram_service import (
    TELEGRAM_BOT_SERVICE
    , TELEGRAM_CHAT_SERVICE
    , TELEGRAM_SERVICE
)

router = APIRouter(prefix="/telegram", tags=["Telegram Bot & Chat Management"])


# ── Telegram Bots CRUD ────────────────────────────────────────────────────────

@router.get(
    "/bots"
    , response_model = RESPONSE_ENVELOPE[TELEGRAM_BOT_LIST_OUT_SCHEMA]
)
def list_telegram_bots(
    search        : Optional[str] = Query(default=None, description="Search by code, name, username, or description")
    , status_code : Optional[str] = Query(default=None)
    , page        : int           = Query(default=1, ge=1)
    , size        : int           = Query(default=50, ge=1, le=200)
    , sort_by     : str           = Query(default="name")
    , sort_order  : str           = Query(default="asc")
    , db          : Session       = Depends(get_db)
):
    data = TELEGRAM_BOT_SERVICE.list_bots(
        db            = db
        , search      = search
        , status_code = status_code
        , page        = page
        , size        = size
        , sort_by     = sort_by
        , sort_order  = sort_order
    )
    return RESPONSE_ENVELOPE.success(
        data      = data
        , message = "Telegram bots retrieved successfully."
    )


@router.get(
    "/bots/{bot_id}"
    , response_model = RESPONSE_ENVELOPE[TELEGRAM_BOT_RESPONSE_SCHEMA]
)
def get_telegram_bot(
    bot_id : str
    , db   : Session = Depends(get_db)
):
    data = TELEGRAM_BOT_SERVICE.get_bot(db=db, bot_id=bot_id)
    return RESPONSE_ENVELOPE.success(
        data      = data
        , message = "Telegram bot retrieved successfully."
    )


@router.post(
    "/bots"
    , response_model = RESPONSE_ENVELOPE[TELEGRAM_BOT_RESPONSE_SCHEMA]
    , status_code    = status.HTTP_201_CREATED
)
def create_telegram_bot(
    body : TELEGRAM_BOT_CREATE_SCHEMA
    , db : Session = Depends(get_db)
):
    data = TELEGRAM_BOT_SERVICE.create_bot(db=db, data=body)
    return RESPONSE_ENVELOPE.created(
        data      = data
        , message = "Telegram bot created successfully."
    )


@router.put(
    "/bots/{bot_id}"
    , response_model = RESPONSE_ENVELOPE[TELEGRAM_BOT_RESPONSE_SCHEMA]
)
def update_telegram_bot(
    bot_id : str
    , body : TELEGRAM_BOT_UPDATE_SCHEMA
    , db   : Session = Depends(get_db)
):
    data = TELEGRAM_BOT_SERVICE.update_bot(db=db, bot_id=bot_id, data=body)
    return RESPONSE_ENVELOPE.success(
        data      = data
        , message = "Telegram bot updated successfully."
    )


@router.delete(
    "/bots/{bot_id}"
    , status_code = status.HTTP_204_NO_CONTENT
)
def delete_telegram_bot(
    bot_id : str
    , db   : Session = Depends(get_db)
):
    TELEGRAM_BOT_SERVICE.delete_bot(db=db, bot_id=bot_id)


# ── Telegram Chats CRUD ───────────────────────────────────────────────────────

@router.get(
    "/chats"
    , response_model = RESPONSE_ENVELOPE[TELEGRAM_CHAT_LIST_OUT_SCHEMA]
)
def list_telegram_chats(
    search              : Optional[str] = Query(default=None)
    , telegram_bot_code : Optional[str] = Query(default=None)
    , chat_type         : Optional[str] = Query(default=None)
    , status_code       : Optional[str] = Query(default=None)
    , page              : int           = Query(default=1, ge=1)
    , size              : int           = Query(default=50, ge=1, le=200)
    , sort_by           : str           = Query(default="name")
    , sort_order        : str           = Query(default="asc")
    , db                : Session       = Depends(get_db)
):
    data = TELEGRAM_CHAT_SERVICE.list_chats(
        db                  = db
        , search            = search
        , telegram_bot_code = telegram_bot_code
        , chat_type         = chat_type
        , status_code       = status_code
        , page              = page
        , size              = size
        , sort_by           = sort_by
        , sort_order        = sort_order
    )
    return RESPONSE_ENVELOPE.success(
        data      = data
        , message = "Telegram chats retrieved successfully."
    )


@router.get(
    "/chats/{chat_id}"
    , response_model = RESPONSE_ENVELOPE[TELEGRAM_CHAT_RESPONSE_SCHEMA]
)
def get_telegram_chat(
    chat_id : str
    , db    : Session = Depends(get_db)
):
    data = TELEGRAM_CHAT_SERVICE.get_chat(db=db, chat_id=chat_id)
    return RESPONSE_ENVELOPE.success(
        data      = data
        , message = "Telegram chat retrieved successfully."
    )


@router.post(
    "/chats"
    , response_model = RESPONSE_ENVELOPE[TELEGRAM_CHAT_RESPONSE_SCHEMA]
    , status_code    = status.HTTP_201_CREATED
)
def create_telegram_chat(
    body : TELEGRAM_CHAT_CREATE_SCHEMA
    , db : Session = Depends(get_db)
):
    data = TELEGRAM_CHAT_SERVICE.create_chat(db=db, data=body)
    return RESPONSE_ENVELOPE.created(
        data      = data
        , message = "Telegram chat created successfully."
    )


@router.put(
    "/chats/{chat_id}"
    , response_model = RESPONSE_ENVELOPE[TELEGRAM_CHAT_RESPONSE_SCHEMA]
)
def update_telegram_chat(
    chat_id : str
    , body  : TELEGRAM_CHAT_UPDATE_SCHEMA
    , db    : Session = Depends(get_db)
):
    data = TELEGRAM_CHAT_SERVICE.update_chat(db=db, chat_id=chat_id, data=body)
    return RESPONSE_ENVELOPE.success(
        data      = data
        , message = "Telegram chat updated successfully."
    )


@router.delete(
    "/chats/{chat_id}"
    , status_code = status.HTTP_204_NO_CONTENT
)
def delete_telegram_chat(
    chat_id : str
    , db    : Session = Depends(get_db)
):
    TELEGRAM_CHAT_SERVICE.delete_chat(db=db, chat_id=chat_id)


@router.post(
    "/send"
    , response_model = RESPONSE_ENVELOPE[Dict[str, Any]]
)
async def send_telegram_message(
    body : TELEGRAM_SEND_MESSAGE_SCHEMA
    , db : Session = Depends(get_db)
):
    result = await TELEGRAM_SERVICE.send_notification(
        chat_code    = body.chat_code
        , text       = body.text
        , parse_mode = body.parse_mode
        , session    = db
    )
    return RESPONSE_ENVELOPE.success(
        data      = result
        , message = "Telegram notification processed."
    )

