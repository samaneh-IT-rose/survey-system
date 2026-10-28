# -*- coding: utf-8 -*-
"""امنیت: هش رمز عبور (PBKDF2-SHA256) و کوکی سشن امضاشده.

- فقط از کتابخانه استاندارد پایتون استفاده می‌شود تا نصب روی سرور ایران
  به هیچ پکیج بیرونی (مثل passlib/bcrypt) وابسته نباشد.
- کلید امضای سشن یک‌بار ساخته و در data/secret.key ذخیره می‌شود؛
  به همین دلیل کوکی‌ها پس از ری‌استارت سرویس معتبر می‌مانند.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from pathlib import Path

from ..config import BASE_DIR

SESSION_COOKIE = "survey_session"
SESSION_TTL_SECONDS = 7 * 24 * 3600  # یک هفته
PBKDF2_ITERATIONS = 120_000

_secret_path = BASE_DIR / "data" / "secret.key"


def get_secret_key() -> str:
    """کلید امضا را می‌خواند؛ اگر نبود می‌سازد (فقط بار اول)."""
    try:
        _secret_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    if _secret_path.exists():
        try:
            key = _secret_path.read_text(encoding="ascii").strip()
            if len(key) >= 32:
                return key
        except OSError:
            pass
    key = secrets.token_hex(32)
    try:
        _secret_path.write_text(key, encoding="ascii")
    except OSError:
        # اگر نوشتن ممکن نبود، کلید موقت این فرایند استفاده می‌شود
        pass
    return key


# ---------- رمز عبور ----------

def hash_password(password: str) -> str:
    """خروجی: pbkdf2_sha256$iterations$salt_hex$hash_hex"""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("pbkdf2_sha256$"):
        return False
    try:
        _, iters, salt, expected = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iters)
        )
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


# ---------- توکن سشن ----------

def make_session_token(user_id: int) -> str:
    expires = int(time.time()) + SESSION_TTL_SECONDS
    payload = f"{user_id}:{expires}"
    sig = hmac.new(get_secret_key().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def read_session_token(token: str | None) -> int | None:
    """شناسهٔ کاربر را برمی‌گرداند؛ توکن نامعتبر یا منقضی → None."""
    if not token:
        return None
    parts = token.split(":")
    if len(parts) != 3:
        return None
    try:
        uid, expires, sig = parts
        payload = f"{uid}:{expires}"
        expected = hmac.new(
            get_secret_key().encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        if int(expires) < time.time():
            return None
        return int(uid)
    except (ValueError, TypeError):
        return None


# ---------- کلید API ----------

def generate_api_key() -> tuple[str, str, str]:
    """کلید جدید می‌سازد؛ خروجی: (کلید کامل، هش، پیشوند)."""
    raw = secrets.token_hex(24)  # 48 نویسه
    key = f"sk_{raw}"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    key_prefix = key[:10]
    return key, key_hash, key_prefix


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()
