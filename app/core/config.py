from __future__ import annotations

import json
from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SETTINGS(BaseSettings):

    model_config = SettingsConfigDict(
        env_file            = ".env"
        , env_file_encoding = "utf-8"
        , case_sensitive    = False
        , extra             = "ignore"
    )

    # ── Enterprise Template Identification & Server Settings ──────────────────
    API_V1_STR                      : str                                           = "/api/v1"
    PROJECT_NAME                    : str                                           = "Clothing Store Management System"
    APP_NAME                        : str                                           = "Clothing Store Management System"
    COMPONENT_NAME                  : str                                           = "clothing_store_api"

    ENV                             : str                                           = "development"
    ENVIRONMENT                     : Literal["development", "staging", "production", "testing"] = "development"
    DEBUG                           : bool                                          = False
    PORT                            : int                                           = 8000

    # ── Security, JWT & System API Key Settings ───────────────────────────────
    SECRET_KEY                      : str                                           = "change_me_at_least_32_characters_long_secret_key"
    AES_SECRET_KEY                  : str                                           = "0123456789abcdef0123456789abcdef"
    ALGORITHM                       : str                                           = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES     : int                                           = 60
    REFRESH_TOKEN_EXPIRE_DAYS       : int                                           = 7
    API_KEY_HEADER_NAME             : str                                           = "X-API-KEY"

    # ── Inbound system/client credential gate ────────────────────────────────
    # Header carrying `Basic <b64(client:secret)>` or `Bearer <token>`; Authorization stays the user JWT.
    SYSTEM_AUTH_HEADER_NAME         : str                                           = "X-System-Authorization"
    # off     : no checking
    # audit   : validate if present, log what would be rejected, never block
    # enforce : reject missing/invalid credentials (401) except allow-listed paths
    # Unset -> "enforce" in production, otherwise "audit".
    SYSTEM_AUTH_MODE                : Optional[Literal["off", "audit", "enforce"]]  = None
    # Extra comma/JSON list of path prefixes exempt from the gate (in addition to the built-in ones).
    SYSTEM_AUTH_PUBLIC_PATHS        : List[str]                                     = []
    WHITE_LIST_CORS                 : List[str]                                     = ["*"]
    BACKEND_CORS_ORIGINS            : List[str]                                     = ["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:3003"]

    @field_validator("BACKEND_CORS_ORIGINS", "WHITE_LIST_CORS", "SYSTEM_AUTH_PUBLIC_PATHS", mode="before")
    @classmethod
    def parse_cors(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("["):
                return json.loads(v_str)
            return [item.strip() for item in v_str.split(",") if item.strip()]
        return v

    # ── PostgreSQL & Template Database Settings ───────────────────────────────
    DB_DIALECT                      : str                                           = "postgresql+psycopg2"
    POSTGRES_HOST                   : str                                           = "localhost"
    POSTGRES_PORT                   : int                                           = 5432
    POSTGRES_DB                     : str                                           = "clothing_store"
    POSTGRES_USER                   : str                                           = "clothing_user"
    POSTGRES_PASSWORD               : str                                           = "change_me"
    DB_SSL                          : str                                           = "disable"

    DB_HOST                         : Optional[str]                                 = None
    DB_PORT                         : Optional[int]                                 = None
    DB_NAME                         : Optional[str]                                 = None
    DB_USER                         : Optional[str]                                 = None
    DB_PASS                         : Optional[str]                                 = None

    @property
    def DATABASE_URL(self) -> str:
        host = self.DB_HOST or self.POSTGRES_HOST
        port = self.DB_PORT or self.POSTGRES_PORT
        name = self.DB_NAME or self.POSTGRES_DB
        user = self.DB_USER or self.POSTGRES_USER
        pwd  = self.DB_PASS or self.POSTGRES_PASSWORD
        return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}"

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        host = self.DB_HOST or self.POSTGRES_HOST
        port = self.DB_PORT or self.POSTGRES_PORT
        name = self.DB_NAME or self.POSTGRES_DB
        user = self.DB_USER or self.POSTGRES_USER
        pwd  = self.DB_PASS or self.POSTGRES_PASSWORD
        return f"postgresql+asyncpg://{user}:{pwd}@{host}:{port}/{name}"

    @property
    def system_auth_mode(self) -> str:
        """Effective gate mode: explicit SYSTEM_AUTH_MODE, else enforce in production / audit elsewhere."""
        if self.SYSTEM_AUTH_MODE:
            return self.SYSTEM_AUTH_MODE
        return "enforce" if self.ENVIRONMENT == "production" else "audit"

    # ── Redis & Task Broker Configuration ─────────────────────────────────────
    REDIS_HOST                      : str                                           = "localhost"
    REDIS_PORT                      : int                                           = 6379
    REDIS_PASSWORD                  : str                                           = "change_me"
    REDIS_DB                        : int                                           = 0
    REDIS_PRODUCT_CACHE_TTL         : int                                           = 300
    REDIS_CACHE_PREFIX              : str                                           = "clothing_store"

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    CELERY_BROKER_URL               : str                                           = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND           : str                                           = "redis://localhost:6379/0"
    REDBEAT_REDIS_URL               : Optional[str]                                 = "redis://localhost:6379/1"

    # ── HTTP Client Pool Settings ─────────────────────────────────────────────
    HTTP_TIMEOUT_SECONDS            : int                                           = 30
    HTTP_CONNECT_TIMEOUT_SECONDS    : int                                           = 10
    HTTP_MAX_CONNECTIONS            : int                                           = 100
    HTTP_MAX_KEEPALIVE_CONNECTIONS  : int                                           = 20

    # ── Audit, Logging & Monitoring ───────────────────────────────────────────
    LOG_LEVEL                       : str                                           = "INFO"
    LOG_RETENTION_DAYS              : int                                           = 90
    ENABLE_ACCESS_AUDIT_LOG         : bool                                          = True
    ENABLE_TRACE_LOG                : bool                                          = True
    ENABLE_TELEGRAM_ALERT           : bool                                          = False
    TELEGRAM_ALERT_CHAT_CODE        : Optional[str]                                 = None

    # ── File Uploads & Store Domain ───────────────────────────────────────────
    UPLOAD_DIR                      : str                                           = "./uploads"
    MAX_UPLOAD_SIZE_MB              : int                                           = 10
    NUXT_PUBLIC_STORE_DOMAIN        : str                                           = "https://store.example.com"

    # ── Seed Credentials (Dev Only) ───────────────────────────────────────────
    SEED_ADMIN_EMAIL                : str                                           = "admin@example.com"
    SEED_ADMIN_PASSWORD             : str                                           = "change_me_admin_password"

    # ── MinIO / Object Storage ────────────────────────────────────────────────
    MINIO_ENDPOINT                  : str                                           = "minio:9000"
    MINIO_ACCESS_KEY                : str                                           = "minioadmin"
    MINIO_SECRET_KEY                : str                                           = "minioadmin123"
    MINIO_BUCKET_NAME               : str                                           = "clothing-store"
    MINIO_USE_SSL                   : bool                                          = False
    MINIO_PUBLIC_URL                : str                                           = "http://localhost:9000"

    # ── ABA PayWay ────────────────────────────────────────────────────────────
    PAYWAY_ENABLED                  : bool                                          = True
    PAYWAY_BASE_URL                 : str                                           = "https://checkout-sandbox.payway.com.kh"
    PAYWAY_MERCHANT_ID              : str                                           = ""
    PAYWAY_PUBLIC_KEY               : str                                           = ""
    PAYWAY_RSA_PUBLIC_KEY           : str                                           = ""
    PAYWAY_RSA_PRIVATE_KEY          : str                                           = ""
    PAYWAY_CALLBACK_BASE_URL        : str                                           = ""
    PAYWAY_QR_LIFETIME_MINUTES      : int                                           = 10

    # ── Telegram Notifications ────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN              : str                                           = ""
    TELEGRAM_GROUP_ID               : str                                           = ""


Settings = SETTINGS


@lru_cache
def get_settings() -> SETTINGS:
    return SETTINGS()


settings = get_settings()
