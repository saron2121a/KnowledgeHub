
"""Redis answer cache (cache-aside). Every Redis failure degrades to 'no cache'.

The corpus version lives in a LOCAL FILE (the source of truth), not in Redis.
If a document changes while Redis is down, the version still increments, so
old cached answers stay unreachable when Redis comes back.
"""
import hashlib
import json
import os
import random
import threading

import redis

from . import config

_VERSION_FILE = config.BASE_DIR / "data" / "corpus_version.txt"
_lock = threading.Lock()
_client = None


def client():
    global _client
    if _client is None:
        _client = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            decode_responses=True,
            socket_timeout=1,
            socket_connect_timeout=1,
        )
    return _client


def corpus_version() -> int:
    try:
        return int(_VERSION_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def bump_version():
    """Make old cached answers unreachable after a corpus change."""
    with _lock:
        _VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _VERSION_FILE.with_suffix(".tmp")
        tmp.write_text(str(corpus_version() + 1))
        os.replace(tmp, _VERSION_FILE)


def make_key(question: str, mode: str, scope: str = "all") -> str:
    """Include corpus version, retrieval mode, document scope and question."""
    norm = " ".join(question.lower().split())
    digest = hashlib.sha256(norm.encode()).hexdigest()
    return f"kh:answer:v{corpus_version()}:{mode}:{scope}:{digest}"


def lookup(question: str, mode: str, scope: str = "all"):
    """Return (key, cached_value_or_None, redis_ok)."""
    key = make_key(question, mode, scope)

    try:
        raw = client().get(key)
    except redis.RedisError:
        return key, None, False

    if not raw:
        return key, None, True

    try:
        value = json.loads(raw)
        if (
            not isinstance(value, dict)
            or "answer" not in value
            or "sources" not in value
        ):
            raise ValueError("malformed cache entry")

        return key, value, True

    except (ValueError, TypeError):
        try:
            client().delete(key)
        except redis.RedisError:
            pass

        return key, None, True


def store(key: str, value: dict):
    if not key:
        return

    try:
        ttl = config.CACHE_TTL + random.randint(
            0, max(0, config.CACHE_TTL // 10)
        )
        client().setex(key, ttl, json.dumps(value))
    except redis.RedisError:
        pass
