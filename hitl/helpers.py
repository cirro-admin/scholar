"""
utils/helpers.py
─────────────────
Shared utility functions: token counter, logger setup, retry decorator, file writer.
"""

from __future__ import annotations
import time, functools, logging
from pathlib import Path


# ── Logger ────────────────────────────────────────────────────────────────────

def get_logger(name: str = "scholar") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s — %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


# ── Retry decorator ───────────────────────────────────────────────────────────

def retry(max_attempts: int = 3, backoff: float = 2.0, exceptions=(Exception,)):
    """Decorator: retry a function up to max_attempts times with exponential backoff."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts:
                        wait = backoff ** (attempt - 1)
                        print(f"[retry] {fn.__name__} attempt {attempt} failed: {e} — retrying in {wait:.1f}s")
                        time.sleep(wait)
            raise last_exc
        return wrapper
    return decorator


# ── Token counter (approximate) ───────────────────────────────────────────────

def count_tokens_approx(text: str) -> int:
    """Rough token count: ~4 characters per token (GPT/Gemini average)."""
    return len(text) // 4


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to approximately max_tokens tokens."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[...truncated]"


# ── File writer ───────────────────────────────────────────────────────────────

def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_text(path: str | Path, content: str, encoding: str = "utf-8") -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(content, encoding=encoding)
    return p
