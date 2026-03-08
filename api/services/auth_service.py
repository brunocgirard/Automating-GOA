"""Authentication services: password hashing, sessions, bootstrap, and Gemini key crypto."""

from __future__ import annotations

import hashlib
import os
import secrets
import hmac
from datetime import datetime, timedelta
from typing import Any

from google import genai as google_genai

from src.utils.db import backfill_ownership, count_users, create_user, find_user_by_username

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerifyMismatchError
    _ARGON2_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - environment guard
    PasswordHasher = None  # type: ignore[assignment]
    InvalidHashError = VerifyMismatchError = Exception  # type: ignore[assignment]
    _ARGON2_IMPORT_ERROR = exc

try:
    from cryptography.fernet import Fernet, InvalidToken
    _FERNET_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - environment guard
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment]
    _FERNET_IMPORT_ERROR = exc


COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "goa_session")
COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
try:
    SESSION_TTL_HOURS = max(int(os.getenv("AUTH_SESSION_TTL_HOURS", "12")), 1)
except ValueError:
    SESSION_TTL_HOURS = 12
SESSION_PEPPER = os.getenv("AUTH_SESSION_PEPPER", "")

_DEFAULT_ROLE = "standard"
_ADMIN_ROLE = "admin"
_KEY_TEST_MODEL = "gemini-2.5-flash-lite"
_PBKDF2_PREFIX = "pbkdf2_sha256"

_PASSWORD_HASHER = PasswordHasher() if PasswordHasher is not None else None
_FERNET_INSTANCE: Fernet | None = None


class AuthBootstrapError(RuntimeError):
    """Raised when admin bootstrap is required but invalid."""


class GeminiKeyError(RuntimeError):
    """Raised when Gemini key encryption/decryption cannot proceed."""


def _now() -> datetime:
    return datetime.now()


def _now_str() -> str:
    return _now().strftime("%Y-%m-%d %H:%M:%S")


def hash_password(plain: str) -> str:
    if _PASSWORD_HASHER is None:
        password_bytes = str(plain or "").encode("utf-8")
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password_bytes, salt, 200_000)
        return f"{_PBKDF2_PREFIX}${salt.hex()}${digest.hex()}"
    return _PASSWORD_HASHER.hash(str(plain or ""))


def verify_password(plain: str, password_hash: str) -> bool:
    normalized_hash = str(password_hash or "")
    if normalized_hash.startswith(f"{_PBKDF2_PREFIX}$"):
        try:
            _, salt_hex, digest_hex = normalized_hash.split("$", 2)
            salt = bytes.fromhex(salt_hex)
            expected_digest = bytes.fromhex(digest_hex)
            check_digest = hashlib.pbkdf2_hmac(
                "sha256",
                str(plain or "").encode("utf-8"),
                salt,
                200_000,
            )
            return hmac.compare_digest(expected_digest, check_digest)
        except Exception:
            return False

    if _PASSWORD_HASHER is None:
        return False
    try:
        return bool(_PASSWORD_HASHER.verify(normalized_hash, str(plain or "")))
    except (VerifyMismatchError, InvalidHashError):
        return False
    except Exception:
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    raw = f"{SESSION_PEPPER}{str(token or '')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_session_expiry() -> datetime:
    return _now() + timedelta(hours=SESSION_TTL_HOURS)


def get_session_expiry_str() -> str:
    return get_session_expiry().strftime("%Y-%m-%d %H:%M:%S")


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    candidates = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    )
    for fmt in candidates:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def is_session_expired(expires_at: str | None) -> bool:
    parsed = parse_datetime(expires_at)
    if parsed is None:
        return True
    return parsed <= _now()


def user_has_gemini_key(user_row: dict[str, Any]) -> bool:
    return bool(str(user_row.get("gemini_api_key_encrypted") or "").strip())


def user_to_response_payload(user_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(user_row["id"]),
        "username": str(user_row.get("username") or ""),
        "display_name": str(user_row.get("display_name") or "").strip() or None,
        "role": str(user_row.get("role") or _DEFAULT_ROLE),
        "is_active": bool(int(user_row.get("is_active") or 0)),
        "has_gemini_key": user_has_gemini_key(user_row),
    }


def _load_fernet() -> Fernet:
    global _FERNET_INSTANCE
    if Fernet is None:
        raise GeminiKeyError(
            "cryptography is required for encrypted Gemini key storage."
            f" Import error: {_FERNET_IMPORT_ERROR}"
        )
    if _FERNET_INSTANCE is not None:
        return _FERNET_INSTANCE

    raw_secret = str(os.getenv("GEMINI_KEY_ENCRYPTION_SECRET") or "").strip()
    if not raw_secret:
        raise GeminiKeyError("GEMINI_KEY_ENCRYPTION_SECRET is not configured.")

    try:
        _FERNET_INSTANCE = Fernet(raw_secret.encode("utf-8"))
    except Exception as exc:
        raise GeminiKeyError("GEMINI_KEY_ENCRYPTION_SECRET is invalid.") from exc
    return _FERNET_INSTANCE


def encrypt_gemini_key(plain_key: str) -> str:
    normalized = str(plain_key or "").strip()
    if not normalized:
        raise GeminiKeyError("API key cannot be empty.")
    fernet = _load_fernet()
    return fernet.encrypt(normalized.encode("utf-8")).decode("utf-8")


def decrypt_gemini_key(encrypted_key: str) -> str:
    normalized = str(encrypted_key or "").strip()
    if not normalized:
        raise GeminiKeyError("Encrypted API key is empty.")
    fernet = _load_fernet()
    try:
        return fernet.decrypt(normalized.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise GeminiKeyError("Stored API key could not be decrypted.") from exc


def test_gemini_api_key(api_key: str) -> tuple[bool, str | None]:
    normalized = str(api_key or "").strip()
    if not normalized:
        return False, "API key is empty."

    try:
        client = google_genai.Client(api_key=normalized)
        if hasattr(client.models, "count_tokens"):
            client.models.count_tokens(model=_KEY_TEST_MODEL, contents="test")
        else:
            client.models.generate_content(model=_KEY_TEST_MODEL, contents="test")
        return True, None
    except Exception as exc:
        return False, str(exc)


def bootstrap_admin_user() -> dict[str, Any] | None:
    if count_users() > 0:
        return None

    username = str(os.getenv("AUTH_BOOTSTRAP_ADMIN_USERNAME", "admin") or "admin").strip() or "admin"
    password = str(os.getenv("AUTH_BOOTSTRAP_ADMIN_PASSWORD") or "").strip()
    display_name = str(os.getenv("AUTH_BOOTSTRAP_ADMIN_DISPLAY_NAME") or username).strip() or username

    if not password:
        raise AuthBootstrapError(
            "AUTH_BOOTSTRAP_ADMIN_PASSWORD is required when no users exist. "
            "Set it in the environment before starting the API."
        )

    existing = find_user_by_username(username)
    if existing:
        return existing

    created = create_user(
        username=username,
        display_name=display_name,
        password_hash=hash_password(password),
        role=_ADMIN_ROLE,
    )
    if not created:
        raise AuthBootstrapError("Failed to bootstrap admin user.")

    backfill_ownership(int(created["id"]))
    return created


def session_cookie_options() -> dict[str, Any]:
    max_age = SESSION_TTL_HOURS * 60 * 60
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "secure": COOKIE_SECURE,
        "samesite": "lax",
        "path": "/",
        "max_age": max_age,
        "expires": max_age,
    }


def now_str() -> str:
    return _now_str()
