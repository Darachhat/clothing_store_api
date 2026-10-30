import base64
import hashlib
import hmac
import secrets
import time
import uuid
from typing import Any, Dict, Optional, Tuple
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")
except ImportError:
    pwd_context = None

from app.core.constants import SENSITIVE_HEADER_KEYS

CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def hash_password(password: str) -> str:
    if pwd_context is not None:
        return pwd_context.hash(password)
    salt   = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password.startswith("pbkdf2_sha256$"):
        try:
            _, salt, digest = hashed_password.split("$", 2)
            computed = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
            return hmac.compare_digest(computed, digest)
        except Exception:
            return False
    if pwd_context is not None:
        return pwd_context.verify(plain_password, hashed_password)
    return hmac.compare_digest(plain_password, hashed_password)


def generate_api_key(prefix: str = "sk_live_") -> str:
    token = secrets.token_hex(24)
    return f"{prefix}{token}"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_ulid() -> str:
    """
    Generate a 26-character Crockford Base32 ULID string (48-bit timestamp + 80-bit randomness).
    """
    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    random_bits  = secrets.randbits(80)
    value        = (timestamp_ms << 80) | random_bits

    chars = []
    for _ in range(26):
        chars.append(CROCKFORD_BASE32[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def generate_uuid4() -> str:
    return str(uuid.uuid4())


def build_basic_auth(username: str, password: str) -> str:
    raw = f"{username}:{password}".encode("utf-8")
    return f"Basic {base64.b64encode(raw).decode('utf-8')}"


def parse_basic_auth(auth_header: Optional[str]) -> Optional[Tuple[str, str]]:
    """
    Parse an HTTP Basic Authorization header into (username, password).
    Returns None if malformed or not Basic auth.
    """
    if not auth_header or not auth_header.lower().startswith("basic "):
        return None
    try:
        encoded = auth_header.split(" ", 1)[1].strip()
        decoded = base64.b64decode(encoded).decode("utf-8")
        if ":" not in decoded:
            return None
        username, password = decoded.split(":", 1)
        return username, password
    except Exception:
        return None


def redact_headers(headers: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Return a copy of headers with sensitive credentials masked as '[REDACTED]'.
    """
    if not headers:
        return {}
    sanitized : Dict[str, Any] = {}
    for k, v in headers.items():
        if str(k).lower() in SENSITIVE_HEADER_KEYS:
            sanitized[str(k)] = "[REDACTED]"
        else:
            sanitized[str(k)] = v
    return sanitized


class CRYPTO_UTILS:
    """
    Cryptographic helper class providing HMAC-SHA256 signing and verification.
    """

    @staticmethod
    def hmac_sha256(secret: str, message: str) -> str:
        return hmac.new(
            secret.encode("utf-8")
            , message.encode("utf-8")
            , hashlib.sha256
        ).hexdigest()

    @staticmethod
    def verify_hmac_sha256(secret: str, message: str, signature: str) -> bool:
        expected = CRYPTO_UTILS.hmac_sha256(secret=secret, message=message)
        return hmac.compare_digest(expected, signature)

