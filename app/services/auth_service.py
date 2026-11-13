"""Authentication service: user JWT auth (login, logout, refresh, change password, Telegram login, phone verification) & system client API key auth."""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enum.common_enum import COMMON_STATUS_ENUM, STATUS_CODE_ENUM
from app.core.exceptions import (
    BAD_REQUEST_EXCEPTION,
    CONFLICT_EXCEPTION,
    FORBIDDEN_EXCEPTION,
    NOT_FOUND_EXCEPTION,
    UNAUTHORIZED_EXCEPTION,
)
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.core.utils.crypto_utils import generate_api_key, hash_api_key
from app.core.utils.phone_utils import normalize_phone_number
from app.core.utils.telegram_auth import verify_telegram_login_data
from app.models import (
    PHONE_VERIFICATION_MODEL,
    SYSTEM_CLIENT_MODEL,
    TELEGRAM_AUTH_REPLAY_MODEL,
    TELEGRAM_BOT_MODEL,
    RefreshToken,
    User,
)
from app.repositories.user_repository import RefreshTokenRepository, UserRepository
from app.schemas.auth_schema import (
    CHANGE_PASSWORD_REQUEST_SCHEMA,
    LOGIN_REQUEST_SCHEMA,
    LOGOUT_REQUEST_SCHEMA,
    REFRESH_REQUEST_SCHEMA,
    SYSTEM_CLIENT_CREATE_SCHEMA,
    SYSTEM_CLIENT_RESPONSE_SCHEMA,
)

logger = get_logger(__name__)

# Sliding-window rate limit buckets: key -> list of epoch timestamps
_RATE_LIMIT_BUCKETS: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_MAX_REQUESTS = 15
RATE_LIMIT_WINDOW_SECONDS = 60
_LAST_TELEGRAM_UPDATE_OFFSET: int = 0


def reset_rate_limits() -> None:
    """Clear in-memory rate limit buckets (used in automated tests)."""
    _RATE_LIMIT_BUCKETS.clear()


def enforce_rate_limit(bucket_key: str, *, max_requests: int = RATE_LIMIT_MAX_REQUESTS, window_seconds: int = RATE_LIMIT_WINDOW_SECONDS) -> None:
    now = time.monotonic()
    cutoff = now - window_seconds
    timestamps = [ts for ts in _RATE_LIMIT_BUCKETS[bucket_key] if ts > cutoff]
    if len(timestamps) >= max_requests:
        _RATE_LIMIT_BUCKETS[bucket_key] = timestamps
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication requests. Please wait before trying again.",
        )
    timestamps.append(now)
    _RATE_LIMIT_BUCKETS[bucket_key] = timestamps



class AUTH_SERVICE:
    """Service orchestrating User RBAC JWT credential issuance, Telegram Auth, Phone Linking, and System Client API keys."""

    reset_rate_limits = staticmethod(reset_rate_limits)
    enforce_rate_limit = staticmethod(enforce_rate_limit)

    def __init__(self, db: AsyncSession) -> None:
        self.db         = db
        self.user_repo  = UserRepository(db)
        self.token_repo = RefreshTokenRepository(db)

    # ── Token Issuance Helper ─────────────────────────────────────────────────

    async def _issue_tokens_for_user(
        self,
        user: User,
        *,
        action: str = "USER_LOGIN",
        request: Optional[Request] = None,
        extra_audit_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        user.last_login_at = datetime.now(UTC)

        access_token  = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))
        token_hash    = hashlib.sha256(refresh_token.encode()).hexdigest()

        ip_addr    = request.client.host if request and request.client else None
        user_agent = request.headers.get("user-agent") if request else None

        rt = RefreshToken(
            user_id    = user.id,
            token_hash = token_hash,
            expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address = ip_addr,
            user_agent = user_agent,
        )
        self.db.add(rt)

        audit_payload = {"username": user.username}
        if extra_audit_data:
            audit_payload.update(extra_audit_data)

        from app.services.audit_service import AUDIT_SERVICE
        await AUDIT_SERVICE.record(
            self.db,
            action      = action,
            entity_type = "user",
            entity_id   = user.id,
            user_id     = user.id,
            ip_address  = ip_addr,
            user_agent  = user_agent,
            new_data    = audit_payload,
        )
        await self.db.commit()
        refreshed = await self.user_repo.get_by_id(user.id)

        return {
            "access_token"  : access_token,
            "refresh_token" : refresh_token,
            "token_type"    : "bearer",
            "user"          : refreshed or user,
        }

    # ── User JWT Authentication (Clothing Store RBAC) ─────────────────────────

    async def login(
        self,
        username : str,
        password : str,
        request  : Optional[Request] = None,
    ) -> Dict[str, Any]:
        identifier = username.strip()
        user = await self.user_repo.get_by_username(identifier)
        if not user and "@" in identifier:
            user = await self.user_repo.get_by_email(identifier.lower())
        if not user:
            try:
                norm_phone = normalize_phone_number(identifier)
                if norm_phone:
                    candidate = await self.user_repo.get_by_phone_number(norm_phone)
                    if candidate and candidate.phone_verified:
                        user = candidate
            except ValueError:
                pass

        if not user or not verify_password(password, user.hashed_password):
            raise UNAUTHORIZED_EXCEPTION("Invalid username or password")

        if user.status != COMMON_STATUS_ENUM.ACTIVE.value:
            raise FORBIDDEN_EXCEPTION("Account is not active")

        return await self._issue_tokens_for_user(user, action="USER_LOGIN", request=request)

    async def refresh(self, refresh_token: str) -> Dict[str, Any]:
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        stored     = await self.token_repo.get_by_hash(token_hash)

        if not stored or stored.revoked:
            raise UNAUTHORIZED_EXCEPTION("Invalid or revoked refresh token")
        if stored.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
            raise UNAUTHORIZED_EXCEPTION("Refresh token expired")

        stored.revoked = True

        user = await self.user_repo.get_by_id(stored.user_id)
        if not user or user.status != COMMON_STATUS_ENUM.ACTIVE.value:
            raise UNAUTHORIZED_EXCEPTION("User not found")

        new_access  = create_access_token(str(user.id))
        new_refresh = create_refresh_token(str(user.id))
        new_hash    = hashlib.sha256(new_refresh.encode()).hexdigest()

        new_rt = RefreshToken(
            user_id    = user.id,
            token_hash = new_hash,
            expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.db.add(new_rt)
        await self.db.commit()

        return {
            "access_token"  : new_access,
            "refresh_token" : new_refresh,
            "token_type"    : "bearer",
        }

    async def logout(self, refresh_token: str) -> None:
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        stored     = await self.token_repo.get_by_hash(token_hash)
        if stored:
            stored.revoked = True
            from app.services.audit_service import AUDIT_SERVICE
            await AUDIT_SERVICE.record(
                self.db,
                action      = "USER_LOGOUT",
                entity_type = "user",
                entity_id   = stored.user_id,
                user_id     = stored.user_id,
                new_data    = {"revoked_token_id": str(stored.id)},
            )
            await self.db.commit()

    async def change_password(
        self,
        user             : User,
        current_password : str,
        new_password     : str,
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise BAD_REQUEST_EXCEPTION("Current password is incorrect")
        user.hashed_password = hash_password(new_password)
        from app.services.audit_service import AUDIT_SERVICE
        await AUDIT_SERVICE.record(
            self.db,
            action      = "USER_PASSWORD_CHANGED",
            entity_type = "user",
            entity_id   = user.id,
            user_id     = user.id,
            new_data    = {"username": user.username},
        )
        await self.db.commit()

    # ── Telegram Login & Identity Linking ─────────────────────────────────────

    async def _resolve_telegram_bot_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Resolve active Telegram bot token and public bot username directly from the DB."""
        stmt = (
            select(TELEGRAM_BOT_MODEL)
            .where(
                TELEGRAM_BOT_MODEL.deleted_datetime.is_(None),
                TELEGRAM_BOT_MODEL.status_code.in_(["active", "ACTIVE"]),
            )
            .order_by(TELEGRAM_BOT_MODEL.created_datetime.desc())
            .limit(1)
        )
        res = await self.db.execute(stmt)
        bot_row = res.scalar_one_or_none()
        token = bot_row.token.strip() if (bot_row and bot_row.token) else None
        bot_username = bot_row.username.strip().lstrip("@") if (bot_row and bot_row.username) else None

        return token, bot_username

    @staticmethod
    def _extract_public_bot_id(token: Optional[str]) -> Optional[str]:
        if not token or ":" not in token:
            return None
        bot_id = token.split(":", 1)[0].strip()
        return bot_id if bot_id.isdigit() else None

    async def get_telegram_config(self) -> Dict[str, Any]:
        token, bot_username = await self._resolve_telegram_bot_credentials()
        return {
            "enabled"      : bool(token),
            "bot_username" : bot_username,
            "bot_id"       : self._extract_public_bot_id(token),
        }

    async def get_telegram_status(self, current_user: Optional[User] = None) -> Dict[str, Any]:
        token, bot_username = await self._resolve_telegram_bot_credentials()
        bot_id = self._extract_public_bot_id(token)
        if not current_user:
            return {
                "enabled"              : bool(token),
                "bot_username"         : bot_username,
                "bot_id"               : bot_id,
                "is_linked"            : False,
                "telegram_is_verified" : False,
                "telegram_id"          : None,
                "telegram_user_id"     : None,
                "telegram_username"    : None,
                "telegram_photo_url"   : None,
                "telegram_linked_at"   : None,
            }
        is_linked = bool(current_user.telegram_id)
        return {
            "enabled"              : bool(token),
            "bot_username"         : bot_username,
            "bot_id"               : bot_id,
            "is_linked"            : is_linked,
            "telegram_is_verified" : bool(is_linked and current_user.telegram_linked_at is not None),
            "telegram_id"          : current_user.telegram_id,
            "telegram_user_id"     : current_user.telegram_id,
            "telegram_username"    : current_user.telegram_username,
            "telegram_photo_url"   : current_user.telegram_photo_url,
            "telegram_linked_at"   : current_user.telegram_linked_at,
        }

    async def _verify_and_record_telegram_payload(
        self,
        auth_data: Dict[str, Any],
        request: Optional[Request] = None,
    ) -> Dict[str, Any]:
        client_ip = request.client.host if request and request.client else "unknown"
        enforce_rate_limit(f"telegram_auth:{client_ip}")

        token, _ = await self._resolve_telegram_bot_credentials()
        if not token:
            raise BAD_REQUEST_EXCEPTION("Telegram authentication is not configured")

        verified = verify_telegram_login_data(
            auth_data,
            token,
            max_age_seconds=settings.TELEGRAM_AUTH_MAX_AGE_SECONDS,
        )

        # Replay check against auth.telegram_auth_replays
        existing_stmt = select(TELEGRAM_AUTH_REPLAY_MODEL.id).where(
            TELEGRAM_AUTH_REPLAY_MODEL.auth_hash == verified["hash"]
        )
        existing_res = await self.db.execute(existing_stmt)
        if existing_res.scalar_one_or_none() is not None:
            raise UNAUTHORIZED_EXCEPTION("Telegram authentication data has already been used (replay rejected)")

        replay_entry = TELEGRAM_AUTH_REPLAY_MODEL(
            auth_hash   = verified["hash"],
            telegram_id = verified["telegram_id"],
            auth_date   = verified["auth_date"],
            expires_at  = datetime.now(UTC) + timedelta(seconds=settings.TELEGRAM_AUTH_MAX_AGE_SECONDS * 2),
            status_code = "ACTIVE",
        )
        self.db.add(replay_entry)
        await self.db.flush()
        return verified

    async def login_with_telegram(
        self,
        auth_data            : Dict[str, Any],
        request              : Optional[Request] = None,
        required_role        : Optional[str] = None,
        auto_create_customer : bool = False,
    ) -> Dict[str, Any]:
        verified = await self._verify_and_record_telegram_payload(auth_data, request=request)
        user = await self.user_repo.get_by_telegram_id(verified["telegram_id"])
        if not user:
            if auto_create_customer:
                from app.models import ROLE_MODEL
                role_res = await self.db.execute(select(ROLE_MODEL).where(ROLE_MODEL.name == "CUSTOMER"))
                customer_role = role_res.scalar_one_or_none()
                if not customer_role:
                    customer_role = ROLE_MODEL(name="CUSTOMER", description="Web store customer", is_system=True)
                    self.db.add(customer_role)
                    await self.db.flush()

                tg_id_str = verified["telegram_id"]
                base_username = verified.get("username") or f"tg_{tg_id_str}"
                candidate_username = base_username
                if await self.user_repo. get_by_username(candidate_username):
                    candidate_username = f"tg_{tg_id_str}"

                full_name_parts = [p for p in (verified.get("first_name"), verified.get("last_name")) if p]
                full_name = " ".join(full_name_parts) if full_name_parts else candidate_username

                user = User(
                    username           = candidate_username,
                    email              = f"tg_{tg_id_str}@telegram.local",
                    full_name          = full_name,
                    hashed_password    = "!telegram_only",
                    telegram_id        = tg_id_str,
                    telegram_username  = verified.get("username"),
                    telegram_photo_url = verified.get("photo_url"),
                    telegram_linked_at = datetime.now(UTC),
                    status             = COMMON_STATUS_ENUM.ACTIVE.value,
                    roles              = [customer_role],
                )
                self.db.add(user)
                await self.db.flush()
            else:
                raise UNAUTHORIZED_EXCEPTION(
                    "No user account is linked to this Telegram identity. Please sign in with your existing credentials first and connect Telegram in your account settings."
                )

        if user.status != COMMON_STATUS_ENUM.ACTIVE.value:
            raise FORBIDDEN_EXCEPTION("Account is not active")

        if required_role:
            role_names = {r.name for r in (user.roles or [])}
            if required_role not in role_names:
                raise FORBIDDEN_EXCEPTION("This account does not have permission for this portal")

        # Keep non-authoritative display metadata fresh
        if verified.get("username"):
            user.telegram_username = verified["username"]
        if verified.get("photo_url"):
            user.telegram_photo_url = verified["photo_url"]

        return await self._issue_tokens_for_user(
            user,
            action="USER_TELEGRAM_LOGIN",
            request=request,
            extra_audit_data={
                "telegram_id": verified["telegram_id"],
                "telegram_username": verified.get("username"),
            },
        )

    async def link_telegram_identity(
        self,
        current_user : User,
        auth_data    : Dict[str, Any],
        request      : Optional[Request] = None,
    ) -> User:
        if current_user.status != COMMON_STATUS_ENUM.ACTIVE.value:
            raise FORBIDDEN_EXCEPTION("Account is not active")

        verified = await self._verify_and_record_telegram_payload(auth_data, request=request)
        telegram_id = verified["telegram_id"]

        if await self.user_repo.telegram_id_exists(telegram_id, exclude_user_id=current_user.id):
            from app.services.audit_service import AUDIT_SERVICE
            await AUDIT_SERVICE.record(
                self.db,
                action      = "USER_TELEGRAM_LINK_CONFLICT",
                entity_type = "user",
                entity_id   = current_user.id,
                user_id     = current_user.id,
                ip_address  = request.client.host if request and request.client else None,
                user_agent  = request.headers.get("user-agent") if request else None,
                new_data    = {
                    "attempted_telegram_id": telegram_id,
                    "reason": "already_linked_to_another_account",
                },
            )
            await self.db.commit()
            raise CONFLICT_EXCEPTION("This Telegram identity is already linked to another user account")

        old_telegram_id = current_user.telegram_id
        current_user.telegram_id        = telegram_id
        current_user.telegram_username  = verified.get("username")
        current_user.telegram_photo_url = verified.get("photo_url")
        current_user.telegram_linked_at = datetime.now(UTC)

        from app.services.audit_service import AUDIT_SERVICE
        await AUDIT_SERVICE.record(
            self.db,
            action      = "USER_TELEGRAM_LINKED",
            entity_type = "user",
            entity_id   = current_user.id,
            user_id     = current_user.id,
            ip_address  = request.client.host if request and request.client else None,
            user_agent  = request.headers.get("user-agent") if request else None,
            old_data    = {"telegram_id": old_telegram_id},
            new_data    = {
                "telegram_id": telegram_id,
                "telegram_username": verified.get("username"),
            },
        )
        await self.db.commit()
        return await self.user_repo.get_by_id(current_user.id)

    async def unlink_telegram_identity(
        self,
        current_user : User,
        request      : Optional[Request] = None,
    ) -> User:
        if not current_user.telegram_id:
            raise BAD_REQUEST_EXCEPTION("No Telegram identity is currently linked to this account")

        old_telegram_id = current_user.telegram_id
        old_username    = current_user.telegram_username
        current_user.telegram_id        = None
        current_user.telegram_username  = None
        current_user.telegram_photo_url = None
        current_user.telegram_linked_at = None

        from app.services.audit_service import AUDIT_SERVICE
        await AUDIT_SERVICE.record(
            self.db,
            action      = "USER_TELEGRAM_UNLINKED",
            entity_type = "user",
            entity_id   = current_user.id,
            user_id     = current_user.id,
            ip_address  = request.client.host if request and request.client else None,
            user_agent  = request.headers.get("user-agent") if request else None,
            old_data    = {"telegram_id": old_telegram_id, "telegram_username": old_username},
            new_data    = {"telegram_id": None},
        )
        await self.db.commit()
        return await self.user_repo.get_by_id(current_user.id)

    # ── Telegram App Deep-Link Login (tg://resolve?domain=...&start=login_...) ─

    async def create_telegram_app_challenge(
        self,
        *,
        mode         : str = "login",
        current_user : Optional[User] = None,
        request      : Optional[Request] = None,
    ) -> Dict[str, Any]:
        token, bot_username = await self._resolve_telegram_bot_credentials()
        if not token or not bot_username:
            raise BAD_REQUEST_EXCEPTION("Telegram bot is not configured")

        clean_username = bot_username.lstrip("@")
        challenge_token = secrets.token_hex(16)
        prefix = "app_link" if mode == "link" else "app_login"
        start_param = f"link_{challenge_token}" if mode == "link" else f"login_{challenge_token}"
        expires_in = 300

        row = TELEGRAM_AUTH_REPLAY_MODEL(
            auth_hash   = f"{prefix}:{challenge_token}",
            telegram_id = "PENDING",
            auth_date   = int(datetime.now(UTC).timestamp()),
            expires_at  = datetime.now(UTC) + timedelta(seconds=expires_in),
            status_code = "PENDING",
            created_by  = str(current_user.id) if current_user else None,
        )
        self.db.add(row)
        await self.db.commit()

        return {
            "challenge_token"    : challenge_token,
            "bot_username"       : clean_username,
            "tg_app_url"         : f"tg://resolve?domain={clean_username}&start={start_param}",
            "tg_web_url"         : f"https://t.me/{clean_username}?start={start_param}",
            "expires_in_seconds" : expires_in,
        }

    async def _resolve_telegram_login_url(self) -> Optional[str]:
        """Portal login URL stored on the active auth.telegram_bot row (None when not set)."""
        stmt = (
            select(TELEGRAM_BOT_MODEL.login_url)
            .where(
                TELEGRAM_BOT_MODEL.deleted_datetime.is_(None),
                TELEGRAM_BOT_MODEL.status_code.in_(["active", "ACTIVE"]),
            )
            .order_by(TELEGRAM_BOT_MODEL.created_datetime.desc())
            .limit(1)
        )
        value = (await self.db.execute(stmt)).scalar_one_or_none()
        return value.strip() if value and value.strip() else None

    @staticmethod
    def _telegram_login_markup(text: str, login_url: Optional[str]) -> Optional[Dict[str, Any]]:
        """Inline login button; None when the bot has no login_url configured."""
        if not login_url:
            return None
        return {
            "inline_keyboard": [[
                {"text": text, "login_url": {"url": login_url, "request_write_access": True}}
            ]],
        }

    @staticmethod
    async def _send_telegram_bot_message(
        token        : str,
        chat_id      : int | str,
        text         : str,
        reply_markup : Optional[Dict[str, Any]] = None,
    ) -> None:
        import httpx
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(url, json=payload)
        except Exception as exc:
            logger.warning(f"Failed to send Telegram bot message to chat {chat_id}: {exc}")

    async def _sync_telegram_bot_updates(
        self,
        token                : str,
        auto_create_customer : bool = False,
    ) -> None:
        global _LAST_TELEGRAM_UPDATE_OFFSET
        import httpx
        import uuid as _uuid

        login_url = await self._resolve_telegram_login_url()

        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params: Dict[str, Any] = {
            "timeout": 0,
            "allowed_updates": '["message"]',
        }
        if _LAST_TELEGRAM_UPDATE_OFFSET > 0:
            params["offset"] = _LAST_TELEGRAM_UPDATE_OFFSET

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    return
                data = resp.json()
        except Exception as exc:
            logger.warning(f"Telegram getUpdates polling error: {exc}")
            return

        if not data.get("ok"):
            return

        updates = data.get("result") or []
        now = datetime.now(UTC)

        for upd in updates:
            update_id = upd.get("update_id", 0)
            if update_id >= _LAST_TELEGRAM_UPDATE_OFFSET:
                _LAST_TELEGRAM_UPDATE_OFFSET = update_id + 1

            msg = upd.get("message")
            if not msg:
                continue

            from_user = msg.get("from") or {}
            tg_id = str(from_user.get("id") or "").strip()
            if not tg_id:
                continue
            tg_username = from_user.get("username")
            first_name = from_user.get("first_name") or ""
            last_name = from_user.get("last_name") or ""
            chat_id = (msg.get("chat") or {}).get("id") or tg_id
            text = (msg.get("text") or "").strip()

            # 1. Handle /start login_<token> or /start link_<token>
            if text.startswith("/start "):
                arg = text.split(" ", 1)[1].strip()
                if arg.startswith("login_"):
                    c_token = arg[len("login_"):]
                    stmt = select(TELEGRAM_AUTH_REPLAY_MODEL).where(
                        TELEGRAM_AUTH_REPLAY_MODEL.auth_hash == f"app_login:{c_token}",
                        TELEGRAM_AUTH_REPLAY_MODEL.expires_at > now,
                    )
                    c_row = (await self.db.execute(stmt)).scalar_one_or_none()
                    if not c_row or c_row.status_code not in ("PENDING", "AWAITING_PHONE"):
                        await self._send_telegram_bot_message(
                            token,
                            chat_id,
                            "This login session has expired or was already used. Please click 'Log in with Telegram' on the website again.",
                            reply_markup={"remove_keyboard": True},
                        )
                        continue

                    existing_user = await self.user_repo.get_by_telegram_id(tg_id)
                    if existing_user:
                        if tg_username:
                            existing_user.telegram_username = tg_username
                        c_row.telegram_id = tg_id
                        c_row.updated_by = tg_username
                        c_row.status_code = "APPROVED"
                        await self.db.commit()
                        await self._send_telegram_bot_message(
                            token,
                            chat_id,
                            f"✅ Login confirmed for @{existing_user.username} ({existing_user.full_name})!\n\nYou can return to your browser or tap below for Seamless Telegram Login:",
                            reply_markup=self._telegram_login_markup("🔐 Seamless Login to Admin Portal", login_url),
                        )
                    else:
                        c_row.telegram_id = f"CHAT:{tg_id}"
                        c_row.updated_by = tg_username
                        c_row.status_code = "AWAITING_PHONE"
                        await self.db.commit()
                        await self._send_telegram_bot_message(
                            token,
                            chat_id,
                            "👋 Welcome to Clothing Store!\n\nTo link your account and sign in, tap the button below to share your verified Telegram phone number:",
                            reply_markup={
                                "keyboard": [[{"text": "📱 Share Phone Number to Link & Sign In", "request_contact": True}]],
                                "resize_keyboard": True,
                                "one_time_keyboard": True,
                            },
                        )

                elif arg.startswith("link_"):
                    c_token = arg[len("link_"):]
                    stmt = select(TELEGRAM_AUTH_REPLAY_MODEL).where(
                        TELEGRAM_AUTH_REPLAY_MODEL.auth_hash == f"app_link:{c_token}",
                        TELEGRAM_AUTH_REPLAY_MODEL.expires_at > now,
                    )
                    c_row = (await self.db.execute(stmt)).scalar_one_or_none()
                    if not c_row or c_row.status_code != "PENDING" or not c_row.created_by:
                        await self._send_telegram_bot_message(
                            token,
                            chat_id,
                            "This account-linking request has expired. Please try again from your account settings.",
                            reply_markup={"remove_keyboard": True},
                        )
                        continue

                    target_user = await self.user_repo.get_by_id(_uuid.UUID(c_row.created_by))
                    if not target_user:
                        continue

                    if await self.user_repo.telegram_id_exists(tg_id, exclude_user_id=target_user.id):
                        c_row.status_code = "REJECTED"
                        c_row.updated_by = "This Telegram account is already linked to another user."
                        await self.db.commit()
                        await self._send_telegram_bot_message(
                            token,
                            chat_id,
                            "❌ This Telegram account is already linked to another user account.",
                            reply_markup={"remove_keyboard": True},
                        )
                        continue

                    target_user.telegram_id = tg_id
                    target_user.telegram_username = tg_username
                    target_user.telegram_linked_at = now
                    c_row.telegram_id = tg_id
                    c_row.updated_by = tg_username
                    c_row.status_code = "APPROVED"
                    await self.db.commit()
                    await self._send_telegram_bot_message(
                        token,
                        chat_id,
                        f"✅ Your Telegram account is now linked to @{target_user.username} ({target_user.full_name})!\n\nYou can return to your browser.",
                        reply_markup={"remove_keyboard": True},
                    )

            # 1b. Handle plain /start command with Seamless Telegram Login (login_url / keyboardButtonUrlAuth)
            elif text == "/start":
                await self._send_telegram_bot_message(
                    token,
                    chat_id,
                    "👋 Welcome to Clothing Store Bot!\n\nTap the button below to log in seamlessly with your Telegram account:",
                    reply_markup=self._telegram_login_markup("🔐 Log in to Admin Portal", login_url),
                )

            # 2. Handle shared contact (request_contact=True) to verify phone & link account
            contact = msg.get("contact")
            if contact:
                contact_user_id = str(contact.get("user_id") or "").strip()
                raw_phone = str(contact.get("phone_number") or "").strip()
                if contact_user_id != tg_id or not raw_phone:
                    await self._send_telegram_bot_message(
                        token,
                        chat_id,
                        "❌ Please use the 'Share Phone Number' button to share your own verified Telegram contact.",
                    )
                    continue

                try:
                    normalized_phone = normalize_phone_number(raw_phone)
                except ValueError:
                    normalized_phone = None

                # Find any pending AWAITING_PHONE challenge for this Telegram user
                pending_stmt = (
                    select(TELEGRAM_AUTH_REPLAY_MODEL)
                    .where(
                        TELEGRAM_AUTH_REPLAY_MODEL.telegram_id == f"CHAT:{tg_id}",
                        TELEGRAM_AUTH_REPLAY_MODEL.status_code == "AWAITING_PHONE",
                        TELEGRAM_AUTH_REPLAY_MODEL.expires_at > now,
                    )
                    .order_by(TELEGRAM_AUTH_REPLAY_MODEL.created_datetime.desc())
                )
                pending_rows = (await self.db.execute(pending_stmt)).scalars().all()
                if not pending_rows:
                    continue

                matched_user = await self.user_repo.get_by_phone_number(normalized_phone) if normalized_phone else None
                if not matched_user and auto_create_customer and normalized_phone:
                    from app.models import ROLE_MODEL
                    role_res = await self.db.execute(select(ROLE_MODEL).where(ROLE_MODEL.name == "CUSTOMER"))
                    customer_role = role_res.scalar_one_or_none()
                    if not customer_role:
                        customer_role = ROLE_MODEL(name="CUSTOMER", description="Web store customer", is_system=True)
                        self.db.add(customer_role)
                        await self.db.flush()

                    base_username = tg_username or f"tg_{tg_id}"
                    candidate_username = base_username
                    if await self.user_repo.get_by_username(candidate_username):
                        candidate_username = f"tg_{tg_id}"
                    full_name = " ".join([p for p in (first_name, last_name) if p]) or candidate_username

                    matched_user = User(
                        username           = candidate_username,
                        email              = f"tg_{tg_id}@telegram.local",
                        full_name          = full_name,
                        hashed_password    = "!telegram_only",
                        phone_number       = normalized_phone,
                        phone_verified_at  = now,
                        telegram_id        = tg_id,
                        telegram_username  = tg_username,
                        telegram_linked_at = now,
                        status             = COMMON_STATUS_ENUM.ACTIVE.value,
                        roles              = [customer_role],
                    )
                    self.db.add(matched_user)
                    await self.db.flush()

                if matched_user:
                    matched_user.telegram_id = tg_id
                    if tg_username:
                        matched_user.telegram_username = tg_username
                    matched_user.telegram_linked_at = now
                    if not matched_user.phone_verified_at:
                        matched_user.phone_verified_at = now

                    for r in pending_rows:
                        r.telegram_id = tg_id
                        r.updated_by = tg_username
                        r.status_code = "APPROVED"

                    from app.services.audit_service import AUDIT_SERVICE
                    await AUDIT_SERVICE.record(
                        self.db,
                        action      = "USER_TELEGRAM_LINKED",
                        entity_type = "user",
                        entity_id   = matched_user.id,
                        user_id     = matched_user.id,
                        new_data    = {
                            "telegram_id": tg_id,
                            "telegram_username": tg_username,
                            "verified_phone": normalized_phone,
                            "method": "telegram_app_contact_share",
                        },
                    )
                    await self.db.commit()
                    await self._send_telegram_bot_message(
                        token,
                        chat_id,
                        f"✅ Phone {normalized_phone} verified and linked to @{matched_user.username} ({matched_user.full_name})!\n\nYou are now signed in — return to your browser.",
                        reply_markup={"remove_keyboard": True},
                    )
                else:
                    for r in pending_rows:
                        r.status_code = "REJECTED"
                        r.updated_by = f"No account found matching phone {normalized_phone or raw_phone}"
                    await self.db.commit()
                    await self._send_telegram_bot_message(
                        token,
                        chat_id,
                        f"❌ No existing account was found matching phone number {normalized_phone or raw_phone}. Please sign in with your username/password first and link Telegram in your account settings.",
                        reply_markup={"remove_keyboard": True},
                    )

    async def check_telegram_app_challenge(
        self,
        challenge_token      : str,
        *,
        request              : Optional[Request] = None,
        required_role        : Optional[str] = None,
        auto_create_customer : bool = False,
    ) -> Dict[str, Any]:
        token, _ = await self._resolve_telegram_bot_credentials()
        if token:
            await self._sync_telegram_bot_updates(token, auto_create_customer=auto_create_customer)

        stmt = select(TELEGRAM_AUTH_REPLAY_MODEL).where(
            TELEGRAM_AUTH_REPLAY_MODEL.auth_hash.in_([
                f"app_login:{challenge_token}",
                f"app_link:{challenge_token}",
            ])
        )
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        if not row:
            raise NOT_FOUND_EXCEPTION("Telegram login challenge not found")

        now = datetime.now(UTC)
        exp = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
        if exp <= now and row.status_code in ("PENDING", "AWAITING_PHONE"):
            row.status_code = "EXPIRED"
            await self.db.commit()
            return {"status": "EXPIRED", "message": "Telegram login session expired. Please try again."}

        if row.status_code == "PENDING":
            return {
                "status": "PENDING",
                "message": "Waiting for you to tap 'Start' in the Telegram app...",
            }

        if row.status_code == "AWAITING_PHONE":
            return {
                "status": "AWAITING_PHONE",
                "message": "Tap 'Share Phone Number to Link & Sign In' inside the Telegram app to verify your account...",
            }

        if row.status_code == "REJECTED":
            return {
                "status": "REJECTED",
                "message": row.updated_by or "Telegram login was declined.",
            }

        if row.status_code == "APPROVED":
            user = await self.user_repo.get_by_telegram_id(row.telegram_id)
            if not user:
                row.status_code = "REJECTED"
                await self.db.commit()
                return {"status": "REJECTED", "message": "Linked user account not found."}

            if user.status != COMMON_STATUS_ENUM.ACTIVE.value:
                row.status_code = "REJECTED"
                await self.db.commit()
                raise FORBIDDEN_EXCEPTION("Account is not active")

            if required_role:
                role_names = {r.name for r in (user.roles or [])}
                if required_role not in role_names:
                    row.status_code = "REJECTED"
                    await self.db.commit()
                    raise FORBIDDEN_EXCEPTION("This account does not have permission for this portal")

            row.status_code = "CONSUMED"
            await self.db.flush()

            tokens = await self._issue_tokens_for_user(
                user,
                action="USER_TELEGRAM_LOGIN",
                request=request,
                extra_audit_data={
                    "telegram_id": user.telegram_id,
                    "telegram_username": user.telegram_username,
                    "method": "telegram_app_deeplink",
                },
            )
            return {
                "status"        : "APPROVED",
                "message"       : "Authenticated via Telegram app",
                "access_token"  : tokens["access_token"],
                "refresh_token" : tokens["refresh_token"],
                "token_type"    : tokens["token_type"],
                "user"          : tokens["user"],
            }

        return {"status": row.status_code, "message": "Session already completed."}

    # ── Verified Phone Number Linking ─────────────────────────────────────────

    @staticmethod
    def _hash_phone_otp(user_id: Any, normalized_phone: str, otp_code: str) -> str:
        payload = f"{user_id}:{normalized_phone}:{otp_code.strip()}"
        return hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def request_phone_verification(
        self,
        current_user : User,
        raw_phone    : str,
        request      : Optional[Request] = None,
    ) -> Dict[str, Any]:
        try:
            normalized_phone = normalize_phone_number(raw_phone)
        except ValueError as exc:
            raise BAD_REQUEST_EXCEPTION(str(exc)) from exc

        if not normalized_phone:
            raise BAD_REQUEST_EXCEPTION("Phone number is required")

        if await self.user_repo.phone_number_exists(normalized_phone, exclude_user_id=current_user.id):
            raise CONFLICT_EXCEPTION("Phone number is already linked to another user account")

        # Expire any prior pending challenges for this user
        await self.db.execute(
            update(PHONE_VERIFICATION_MODEL)
            .where(
                PHONE_VERIFICATION_MODEL.user_id == current_user.id,
                PHONE_VERIFICATION_MODEL.status_code == "PENDING",
            )
            .values(status_code="EXPIRED")
        )

        otp_code   = f"{secrets.randbelow(900000) + 100000:06d}"
        otp_hash   = self._hash_phone_otp(current_user.id, normalized_phone, otp_code)
        expires_in = settings.PHONE_OTP_EXPIRE_MINUTES * 60
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        challenge = PHONE_VERIFICATION_MODEL(
            user_id      = current_user.id,
            phone_number = normalized_phone,
            otp_hash     = otp_hash,
            expires_at   = expires_at,
            attempts     = 0,
            status_code  = "PENDING",
        )
        self.db.add(challenge)

        from app.services.audit_service import AUDIT_SERVICE
        await AUDIT_SERVICE.record(
            self.db,
            action      = "USER_PHONE_VERIFICATION_REQUESTED",
            entity_type = "user",
            entity_id   = current_user.id,
            user_id     = current_user.id,
            ip_address  = request.client.host if request and request.client else None,
            user_agent  = request.headers.get("user-agent") if request else None,
            new_data    = {"phone_number": normalized_phone},
        )
        await self.db.commit()

        # Best-effort delivery to user's linked Telegram chat if configured
        delivery_channel = "verification_challenge"
        if current_user.telegram_id:
            token, _ = await self._resolve_telegram_bot_credentials()
            if token:
                delivery_channel = "telegram"
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        await client.post(
                            f"https://api.telegram.org/bot{token}/sendMessage",
                            json={
                                "chat_id": current_user.telegram_id,
                                "text": (
                                    f"Phone verification code for {normalized_phone}: {otp_code}\n"
                                    f"Expires in {settings.PHONE_OTP_EXPIRE_MINUTES} minutes."
                                ),
                            },
                        )
                except Exception:
                    logger.warning("Could not deliver OTP via Telegram message; challenge stored in DB.")

        return {
            "message"            : "Verification code issued. Confirm the OTP to link this phone number.",
            "normalized_phone"   : normalized_phone,
            "expires_in_seconds" : expires_in,
            "delivery_channel"   : delivery_channel,
        }

    async def verify_and_link_phone(
        self,
        current_user : User,
        raw_phone    : str,
        otp_code     : str,
        request      : Optional[Request] = None,
    ) -> User:
        try:
            normalized_phone = normalize_phone_number(raw_phone)
        except ValueError as exc:
            raise BAD_REQUEST_EXCEPTION(str(exc)) from exc

        if not normalized_phone:
            raise BAD_REQUEST_EXCEPTION("Phone number is required")

        if await self.user_repo.phone_number_exists(normalized_phone, exclude_user_id=current_user.id):
            raise CONFLICT_EXCEPTION("Phone number is already linked to another user account")

        stmt = (
            select(PHONE_VERIFICATION_MODEL)
            .where(
                PHONE_VERIFICATION_MODEL.user_id == current_user.id,
                PHONE_VERIFICATION_MODEL.phone_number == normalized_phone,
                PHONE_VERIFICATION_MODEL.status_code == "PENDING",
            )
            .order_by(PHONE_VERIFICATION_MODEL.created_datetime.desc())
            .limit(1)
        )
        res = await self.db.execute(stmt)
        challenge = res.scalar_one_or_none()

        if not challenge:
            raise BAD_REQUEST_EXCEPTION("No pending verification challenge found for this phone number")

        if challenge.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
            challenge.status_code = "EXPIRED"
            await self.db.commit()
            raise BAD_REQUEST_EXCEPTION("Phone verification code has expired")

        if challenge.attempts >= settings.PHONE_OTP_MAX_ATTEMPTS:
            challenge.status_code = "LOCKED"
            await self.db.commit()
            raise BAD_REQUEST_EXCEPTION("Maximum verification attempts exceeded. Please request a new code.")

        challenge.attempts += 1
        expected_hash = self._hash_phone_otp(current_user.id, normalized_phone, otp_code)
        if not hmac.compare_digest(expected_hash, challenge.otp_hash):
            await self.db.commit()
            raise BAD_REQUEST_EXCEPTION("Invalid phone verification code")

        now = datetime.now(UTC)
        challenge.status_code = "VERIFIED"
        challenge.verified_at = now

        old_phone = current_user.phone_number
        current_user.phone_number      = normalized_phone
        current_user.phone_verified_at = now

        from app.services.audit_service import AUDIT_SERVICE
        await AUDIT_SERVICE.record(
            self.db,
            action      = "USER_PHONE_LINKED",
            entity_type = "user",
            entity_id   = current_user.id,
            user_id     = current_user.id,
            ip_address  = request.client.host if request and request.client else None,
            user_agent  = request.headers.get("user-agent") if request else None,
            old_data    = {"phone_number": old_phone},
            new_data    = {"phone_number": normalized_phone, "phone_verified": True},
        )
        await self.db.commit()
        return await self.user_repo.get_by_id(current_user.id)

    async def login_payload(
        self,
        payload : LOGIN_REQUEST_SCHEMA,
        request : Optional[Request] = None,
    ) -> Dict[str, Any]:
        """Authenticate user using structured LOGIN_REQUEST_SCHEMA."""
        return await self.login(
            username = payload.username,
            password = payload.password,
            request  = request,
        )

    async def refresh_payload(
        self,
        payload : REFRESH_REQUEST_SCHEMA,
    ) -> Dict[str, Any]:
        """Refresh JWT tokens using structured REFRESH_REQUEST_SCHEMA."""
        return await self.refresh(refresh_token=payload.refresh_token)

    async def logout_payload(
        self,
        payload : LOGOUT_REQUEST_SCHEMA,
    ) -> None:
        """Revoke refresh token using structured LOGOUT_REQUEST_SCHEMA."""
        await self.logout(refresh_token=payload.refresh_token)

    async def change_password_payload(
        self,
        user    : User,
        payload : CHANGE_PASSWORD_REQUEST_SCHEMA,
    ) -> None:
        """Update user password using structured CHANGE_PASSWORD_REQUEST_SCHEMA."""
        await self.change_password(
            user             = user,
            current_password = payload.current_password,
            new_password     = payload.new_password,
        )

    # ── System Client API Key Authentication (Enterprise Template) ────────────

    @staticmethod
    def create_system_client(
        db   : Session,
        data : SYSTEM_CLIENT_CREATE_SCHEMA,
    ) -> Tuple[SYSTEM_CLIENT_MODEL, str]:
        existing = (
            db.query(SYSTEM_CLIENT_MODEL)
            .filter(
                SYSTEM_CLIENT_MODEL.code == data.code,
                SYSTEM_CLIENT_MODEL.deleted_datetime.is_(None),
            )
            .first()
        )
        if existing:
            raise BAD_REQUEST_EXCEPTION(f"System client code '{data.code}' is already registered.")

        raw_api_key  = generate_api_key()
        api_key_hash = hash_api_key(raw_api_key)

        client = SYSTEM_CLIENT_MODEL(
            code         = data.code,
            name         = data.name,
            api_key_hash = api_key_hash,
            description  = data.description,
            status_code  = STATUS_CODE_ENUM.ACTIVE.value,
            created_by   = "admin",
        )
        db.add(client)
        db.commit()
        db.refresh(client)

        return client, raw_api_key

    @staticmethod
    def list_system_clients(db: Session) -> List[SYSTEM_CLIENT_RESPONSE_SCHEMA]:
        rows = (
            db.query(SYSTEM_CLIENT_MODEL)
            .filter(SYSTEM_CLIENT_MODEL.deleted_datetime.is_(None))
            .order_by(SYSTEM_CLIENT_MODEL.created_datetime.desc())
            .all()
        )
        return [SYSTEM_CLIENT_RESPONSE_SCHEMA.model_validate(r) for r in rows]

    @staticmethod
    def revoke_system_client(
        db   : Session,
        code : str,
    ) -> SYSTEM_CLIENT_RESPONSE_SCHEMA:
        client = (
            db.query(SYSTEM_CLIENT_MODEL)
            .filter(
                SYSTEM_CLIENT_MODEL.code == code,
                SYSTEM_CLIENT_MODEL.deleted_datetime.is_(None),
            )
            .first()
        )
        if not client:
            raise NOT_FOUND_EXCEPTION(f"System client '{code}' was not found.")

        client.status_code      = STATUS_CODE_ENUM.INACTIVE.value
        client.updated_datetime = datetime.now(timezone.utc)
        client.updated_by       = "admin"
        db.commit()
        db.refresh(client)
        return SYSTEM_CLIENT_RESPONSE_SCHEMA.model_validate(client)

    @staticmethod
    def verify_api_key(
        db          : Session,
        client_code : str,
        raw_api_key : str,
    ) -> bool:
        client = (
            db.query(SYSTEM_CLIENT_MODEL)
            .filter(
                SYSTEM_CLIENT_MODEL.code == client_code,
                SYSTEM_CLIENT_MODEL.deleted_datetime.is_(None),
                SYSTEM_CLIENT_MODEL.status_code.in_([STATUS_CODE_ENUM.ACTIVE.value, COMMON_STATUS_ENUM.ACTIVE.value]),
            )
            .first()
        )

        if not client:
            return False

        return client.api_key_hash == hash_api_key(raw_api_key)
