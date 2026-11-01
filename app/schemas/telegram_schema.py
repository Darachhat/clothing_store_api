from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.base_schema import STATS_SUMMARY_SCHEMA


# ── Telegram Bot (auth.telegram_bot) Schemas ──────────────────────────────────

class TELEGRAM_BOT_CREATE_SCHEMA(BaseModel):
    code        : str           = Field(..., max_length=100, examples=["alert_bot"])
    name        : str           = Field(..., max_length=255, examples=["System Alert Bot"])
    user_id     : Optional[str] = Field(default=None, max_length=100)
    username    : Optional[str] = Field(default=None, max_length=100)
    token       : Optional[str] = Field(default=None)
    description : Optional[str] = Field(default=None)
    status_code : str           = Field(default="active", max_length=10)


class TELEGRAM_BOT_UPDATE_SCHEMA(BaseModel):
    code        : Optional[str] = Field(default=None, max_length=100)
    name        : Optional[str] = Field(default=None, max_length=255)
    user_id     : Optional[str] = Field(default=None, max_length=100)
    username    : Optional[str] = Field(default=None, max_length=100)
    token       : Optional[str] = Field(default=None)
    description : Optional[str] = Field(default=None)
    status_code : Optional[str] = Field(default=None, max_length=10)


class TELEGRAM_BOT_RESPONSE_SCHEMA(BaseModel):
    id               : str
    code             : str
    name             : str
    user_id          : Optional[str]      = None
    username         : Optional[str]      = None
    token            : Optional[str]      = None
    description      : Optional[str]      = None
    status_code      : str
    created_datetime : Optional[datetime] = None
    updated_datetime : Optional[datetime] = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context) -> None:
        if self.token and len(self.token) > 8 and not self.token.startswith("***"):
            self.token = f"***{self.token[-4:]}"


class TELEGRAM_BOT_LIST_OUT_SCHEMA(BaseModel):
    items : List[TELEGRAM_BOT_RESPONSE_SCHEMA]
    total : int
    page  : int
    size  : int
    stats : STATS_SUMMARY_SCHEMA


# ── Telegram Chat (auth.telegram_chat) Schemas ────────────────────────────────

class TELEGRAM_CHAT_CREATE_SCHEMA(BaseModel):
    code              : str           = Field(..., max_length=100, examples=["ops_alert_chat"])
    telegram_bot_code : str           = Field(..., max_length=100, examples=["alert_bot"])
    name              : str           = Field(..., max_length=255, examples=["Operations Alert Group"])
    chat_type         : Optional[str] = Field(default="group", max_length=50, description="channel | group | topic")
    link              : Optional[str] = Field(default=None, max_length=500)
    chat_id           : Optional[str] = Field(default=None, max_length=100)
    thread_id         : Optional[str] = Field(default=None, max_length=100)
    description       : Optional[str] = Field(default=None)
    status_code       : str           = Field(default="active", max_length=10)


class TELEGRAM_CHAT_UPDATE_SCHEMA(BaseModel):
    code              : Optional[str] = Field(default=None, max_length=100)
    telegram_bot_code : Optional[str] = Field(default=None, max_length=100)
    name              : Optional[str] = Field(default=None, max_length=255)
    chat_type         : Optional[str] = Field(default=None, max_length=50)
    link              : Optional[str] = Field(default=None, max_length=500)
    chat_id           : Optional[str] = Field(default=None, max_length=100)
    thread_id         : Optional[str] = Field(default=None, max_length=100)
    description       : Optional[str] = Field(default=None)
    status_code       : Optional[str] = Field(default=None, max_length=10)


class TELEGRAM_CHAT_RESPONSE_SCHEMA(BaseModel):
    id                : str
    code              : str
    telegram_bot_code : str
    name              : str
    chat_type         : Optional[str]      = None
    link              : Optional[str]      = None
    chat_id           : Optional[str]      = None
    thread_id         : Optional[str]      = None
    description       : Optional[str]      = None
    status_code       : str
    created_datetime  : Optional[datetime] = None
    updated_datetime  : Optional[datetime] = None

    model_config = {"from_attributes": True}


class TELEGRAM_CHAT_LIST_OUT_SCHEMA(BaseModel):
    items : List[TELEGRAM_CHAT_RESPONSE_SCHEMA]
    total : int
    page  : int
    size  : int
    stats : STATS_SUMMARY_SCHEMA


class TELEGRAM_SEND_MESSAGE_SCHEMA(BaseModel):
    chat_code  : str = Field(..., max_length=100, description="Target telegram_chat code")
    text       : str = Field(..., min_length=1, description="Message text to send")
    parse_mode : str = Field(default="HTML", description="HTML or Markdown")

