"""Signed, expiring URLs for citizen uploads.

Uploaded evidence/resolution proofs are no longer served as public static
files. API responses that are already authorised hand out a short-lived
signed URL, which <img>/<video> tags can use without custom headers.
"""
import hashlib
import hmac
import os
import time

from app.config import SECRET_KEY

MEDIA_URL_TTL_SECONDS = int(os.getenv("MEDIA_URL_TTL_SECONDS", "3600"))


def _basename(path: str) -> str:
    # Stored paths may be "uploads/x.jpg", "uploads\\x.jpg" or just "x.jpg".
    return (path or "").replace("\\", "/").rsplit("/", 1)[-1]


def _sig(filename: str, exp: int) -> str:
    key = (SECRET_KEY or "").encode()
    return hmac.new(key, f"media:{filename}:{exp}".encode(), hashlib.sha256).hexdigest()


def verify_media_token(filename: str, token: str | None) -> bool:
    try:
        exp_s, sig = (token or "").split(".", 1)
        exp = int(exp_s)
    except ValueError:
        return False
    if exp < time.time():
        return False
    return hmac.compare_digest(sig, _sig(filename, exp))


def signed_media_url(path: str | None) -> str | None:
    """Return 'uploads/<file>?t=<exp>.<sig>' (relative, like the old media_url)."""
    name = _basename(path or "")
    if not name:
        return None
    exp = int(time.time()) + MEDIA_URL_TTL_SECONDS
    return f"uploads/{name}?t={exp}.{_sig(name, exp)}"
