"""Lightweight cache. Uses Redis if reachable, falls back to in-memory dict."""

from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings
from app.logging import get_logger

log = get_logger(__name__)


class _Cache:
    async def get(self, key: str) -> Any:
        raise NotImplementedError

    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        raise NotImplementedError


class InMemoryCache(_Cache):
    def __init__(self) -> None:
        self._d: dict[str, tuple[str, float]] = {}  # key -> (json_value, expires_at)

    async def get(self, key: str) -> Any:
        entry = self._d.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._d[key]
            return None
        return json.loads(value)

    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        self._d[key] = (json.dumps(value), time.monotonic() + ttl_seconds)


class RedisCache(_Cache):
    def __init__(self, client: aioredis.Redis) -> None:
        self.client = client

    async def get(self, key: str) -> Any:
        try:
            v = await self.client.get(key)
            return json.loads(v) if v else None
        except Exception as e:
            log.warning("cache.redis.get_failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        try:
            await self.client.set(key, json.dumps(value), ex=ttl_seconds)
        except Exception as e:
            log.warning("cache.redis.set_failed", key=key, error=str(e))


_cache: _Cache | None = None


def get_cache() -> _Cache:
    global _cache
    if _cache is not None:
        return _cache
    settings = get_settings()
    try:
        client = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            decode_responses=True,
        )
        _cache = RedisCache(client)
        log.info("cache.redis.init", host=settings.redis_host)
    except Exception as e:
        log.warning("cache.redis.unavailable", error=str(e))
        _cache = InMemoryCache()
    return _cache
