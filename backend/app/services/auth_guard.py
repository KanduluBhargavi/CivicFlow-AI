import os
import hashlib
import threading
import time
from collections import defaultdict, deque


MAX_FAILURES = 5
FAILURE_WINDOW_SECONDS = 15 * 60
LOCKOUT_SECONDS = 15 * 60

_LOCK = threading.Lock()
_FAILURES = defaultdict(deque)
_LOCKED_UNTIL = {}


def _key(identifier: str, ip: str | None):
    return f"{(identifier or '').strip().lower()}|{ip or 'unknown'}"



_REDIS = None
if os.getenv("REDIS_URL"):
    import redis
    _REDIS = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True, socket_connect_timeout=3)

def _redis_key(identifier, ip):
    # Do not expose identifiers in Redis key names.
    digest = hashlib.sha256(_key(identifier, ip).encode()).hexdigest()
    return "civic:login:" + digest

def _prune(key, now):
    q = _FAILURES[key]
    while q and now - q[0] > FAILURE_WINDOW_SECONDS:
        q.popleft()


def assert_login_allowed(identifier: str, ip: str | None):
    if _REDIS is not None:
        ttl = _REDIS.ttl(_redis_key(identifier, ip) + ":lock")
        return (False, ttl) if ttl > 0 else (True, 0)
    now = time.time()
    key = _key(identifier, ip)
    with _LOCK:
        locked_until = _LOCKED_UNTIL.get(key, 0)
        if locked_until > now:
            retry = max(1, int(locked_until - now))
            return False, retry
        if locked_until:
            _LOCKED_UNTIL.pop(key, None)
        _prune(key, now)
    return True, 0


def record_login_failure(identifier: str, ip: str | None):
    if _REDIS is not None:
        key = _redis_key(identifier, ip)
        with _REDIS.pipeline() as pipe:
            pipe.incr(key)
            pipe.expire(key, FAILURE_WINDOW_SECONDS, nx=True)
            count, _ = pipe.execute()
        if count >= MAX_FAILURES:
            _REDIS.setex(key + ":lock", LOCKOUT_SECONDS, "1")
            _REDIS.delete(key)
            return True, LOCKOUT_SECONDS
        return False, 0
    now = time.time()
    key = _key(identifier, ip)
    with _LOCK:
        _prune(key, now)
        _FAILURES[key].append(now)
        if len(_FAILURES[key]) >= MAX_FAILURES:
            _LOCKED_UNTIL[key] = now + LOCKOUT_SECONDS
            _FAILURES[key].clear()
            return True, LOCKOUT_SECONDS
    return False, 0


def clear_login_failures(identifier: str, ip: str | None):
    if _REDIS is not None:
        key = _redis_key(identifier, ip)
        _REDIS.delete(key, key + ":lock")
        return
    key = _key(identifier, ip)
    with _LOCK:
        _FAILURES.pop(key, None)
        _LOCKED_UNTIL.pop(key, None)
