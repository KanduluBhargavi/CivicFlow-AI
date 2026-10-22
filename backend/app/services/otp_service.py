import hashlib
import hmac
import os
import secrets
import threading
import time
import json
from contextlib import contextmanager


OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "300"))
OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "60"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
OTP_PEPPER = os.getenv("OTP_PEPPER") or os.getenv("SECRET_KEY", "civicflow-dev-otp-pepper")

_LOCK = threading.Lock()
_CHALLENGES = {}


# Redis is used when configured, including for multi-worker deployments.
_REDIS = None
if os.getenv("REDIS_URL"):
    import redis
    _REDIS = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True, socket_connect_timeout=3)

class _ChallengeStore(dict):
    def get(self, key, default=None):
        if _REDIS is None: return super().get(key, default)
        raw = _REDIS.get("civic:otp:" + key)
        return json.loads(raw) if raw is not None else default
    def __setitem__(self, key, value):
        if _REDIS is None: return super().__setitem__(key, value)
        ttl = max(1, int(value["expires_at"] - time.time()) + 1)
        _REDIS.setex("civic:otp:" + key, ttl, json.dumps(value))
    def pop(self, key, default=None):
        if _REDIS is None: return super().pop(key, default)
        old = self.get(key, default)
        _REDIS.delete("civic:otp:" + key)
        return old
    def items(self):
        if _REDIS is None: return super().items()
        return []  # Redis handles expiry itself

_CHALLENGES = _ChallengeStore()

@contextmanager
def _challenge_lock():
    if _REDIS is not None:
        with _REDIS.lock("civic:otp:lock", timeout=12, blocking_timeout=5):
            yield
    else:
        with _LOCK:
            yield

def _now():
    return time.time()


def _otp_hash(challenge_id: str, otp: str) -> str:
    raw = f"{challenge_id}:{otp}:{OTP_PEPPER}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _new_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _cleanup_expired():
    now = _now()
    expired = [
        cid for cid, record in _CHALLENGES.items()
        if record["expires_at"] <= now
    ]
    for cid in expired:
        _CHALLENGES.pop(cid, None)


def mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[:1] + "*"
    else:
        masked_local = local[:2] + ("*" * max(2, len(local) - 2))
    return f"{masked_local}@{domain}"


def create_otp_challenge(email: str, purpose: str, context: dict):
    challenge_id = secrets.token_urlsafe(32)
    otp = _new_otp()
    now = _now()

    record = {
        "email": email,
        "purpose": purpose,
        "context": context,
        "otp_hash": _otp_hash(challenge_id, otp),
        "expires_at": now + OTP_TTL_SECONDS,
        "resend_available_at": now + OTP_RESEND_COOLDOWN_SECONDS,
        "attempts_left": OTP_MAX_ATTEMPTS,
    }

    with _challenge_lock():
        _cleanup_expired()
        _CHALLENGES[challenge_id] = record

    return {
        "challenge_id": challenge_id,
        "otp": otp,
        "masked_email": mask_email(email),
        "expires_in": OTP_TTL_SECONDS,
        "resend_after": OTP_RESEND_COOLDOWN_SECONDS,
    }


def verify_otp_challenge(challenge_id: str, otp: str, purpose: str):
    with _challenge_lock():
        _cleanup_expired()
        record = _CHALLENGES.get(challenge_id)

        if not record or record["purpose"] != purpose:
            return {
                "ok": False,
                "status": 400,
                "detail": "OTP session expired or invalid. Please start again.",
            }

        supplied = _otp_hash(challenge_id, otp.strip())
        if not hmac.compare_digest(supplied, record["otp_hash"]):
            record["attempts_left"] -= 1
            _CHALLENGES[challenge_id] = record
            remaining = record["attempts_left"]

            if remaining <= 0:
                _CHALLENGES.pop(challenge_id, None)
                return {
                    "ok": False,
                    "status": 429,
                    "detail": "Too many incorrect OTP attempts. Please start again.",
                }

            return {
                "ok": False,
                "status": 400,
                "detail": f"Incorrect OTP. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
            }

        result = {
            "ok": True,
            "email": record["email"],
            "context": record["context"],
        }
        _CHALLENGES.pop(challenge_id, None)
        return result


def resend_otp_challenge(challenge_id: str, purpose: str):
    now = _now()

    with _challenge_lock():
        _cleanup_expired()
        record = _CHALLENGES.get(challenge_id)

        if not record or record["purpose"] != purpose:
            return {
                "ok": False,
                "status": 400,
                "detail": "OTP session expired or invalid. Please start again.",
            }

        wait = int(record["resend_available_at"] - now)
        if wait > 0:
            return {
                "ok": False,
                "status": 429,
                "detail": f"Please wait {wait} seconds before requesting another OTP.",
                "retry_after": wait,
            }

        otp = _new_otp()
        record["otp_hash"] = _otp_hash(challenge_id, otp)
        record["expires_at"] = now + OTP_TTL_SECONDS
        record["resend_available_at"] = now + OTP_RESEND_COOLDOWN_SECONDS
        record["attempts_left"] = OTP_MAX_ATTEMPTS
        _CHALLENGES[challenge_id] = record

        return {
            "ok": True,
            "otp": otp,
            "email": record["email"],
            "masked_email": mask_email(record["email"]),
            "expires_in": OTP_TTL_SECONDS,
            "resend_after": OTP_RESEND_COOLDOWN_SECONDS,
        }
