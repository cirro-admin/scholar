"""
utils/rate_limiter.py
──────────────────────
Shared rate limiter for external APIs.

In single-user (CLI) mode: uses in-process time tracking.
In multi-user (web/worker) mode: uses Redis token buckets so ALL worker
processes share one counter per API — prevents bans when running parallel jobs.

Usage:
    from utils.rate_limiter import rate_limit

    @rate_limit("arxiv", min_interval=4.0)
    def call_arxiv(query):
        ...

    # Or as a context manager:
    with RateLimiter.get("semantic_scholar"):
        resp = requests.get(...)
"""

from __future__ import annotations
import time, os
from contextlib import contextmanager
from typing import Optional


# ── Config ────────────────────────────────────────────────────────────────────

# Minimum seconds between requests per service
API_LIMITS: dict[str, float] = {
    "arxiv":            4.0,    # arXiv asks for 3s; we use 4s
    "semantic_scholar": 1.1,    # 1 req/sec authenticated; 1.1s safety margin
    "perplexity":       0.5,    # generous; paid API
    "serpapi":          0.5,
    "youtube":          0.5,
    "github":           0.2,
}


# ── Backend selection ─────────────────────────────────────────────────────────

def _redis_available() -> bool:
    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"),
                           socket_connect_timeout=1)
        r.ping()
        return True
    except Exception:
        return False


# ── In-process fallback (single-user / no Redis) ──────────────────────────────

_LOCAL_LAST: dict[str, float] = {}

def _local_wait(service: str) -> None:
    min_interval = API_LIMITS.get(service, 0.5)
    last         = _LOCAL_LAST.get(service, 0.0)
    elapsed      = time.time() - last
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _LOCAL_LAST[service] = time.time()


# ── Redis backend (multi-user / shared across workers) ────────────────────────

def _redis_wait(service: str) -> None:
    """
    Distributed rate limit using Redis SET NX with TTL.
    Blocks until the lock is acquired, then sets the TTL for the next caller.
    """
    import redis
    min_interval = API_LIMITS.get(service, 0.5)
    key          = f"rate_limit:{service}"
    r            = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    ttl_ms       = int(min_interval * 1000)

    while True:
        # Try to set the key (NX = only if not exists, PX = TTL in ms)
        acquired = r.set(key, "1", nx=True, px=ttl_ms)
        if acquired:
            return   # we have the slot
        # Key exists — check TTL and sleep accordingly
        remaining = r.pttl(key)
        sleep_ms  = max(remaining, 50)   # at least 50ms to avoid busy loop
        time.sleep(sleep_ms / 1000)


# ── Public interface ──────────────────────────────────────────────────────────

_use_redis: Optional[bool] = None

def _should_use_redis() -> bool:
    global _use_redis
    if _use_redis is None:
        _use_redis = _redis_available()
        if _use_redis:
            print("[rate_limiter] Using Redis for distributed rate limiting")
        else:
            print("[rate_limiter] Redis not available — using in-process rate limiting")
    return _use_redis


def wait_for(service: str) -> None:
    """Block until it's safe to call the given service."""
    if _should_use_redis():
        try:
            _redis_wait(service)
            return
        except Exception:
            pass   # Redis failed mid-run — fall back to local
    _local_wait(service)


def rate_limit(service: str, min_interval: Optional[float] = None):
    """
    Decorator that enforces rate limiting before every call.

    @rate_limit("arxiv")
    def search_arxiv(query): ...
    """
    if min_interval is not None:
        API_LIMITS[service] = min_interval

    def decorator(fn):
        def wrapper(*args, **kwargs):
            wait_for(service)
            return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__
        return wrapper
    return decorator


@contextmanager
def limited(service: str):
    """Context manager version: `with limited('arxiv'): ...`"""
    wait_for(service)
    yield
