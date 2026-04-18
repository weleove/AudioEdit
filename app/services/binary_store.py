from __future__ import annotations

import time
from threading import Lock

from app.config import Settings

try:
    import redis
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover - depends on optional runtime dependency
    redis = None

    class RedisError(Exception):
        pass


class BinaryStoreError(RuntimeError):
    pass


class BinaryStore:
    def append_bytes(self, key: str, data: bytes) -> None:
        raise NotImplementedError

    def set_bytes(self, key: str, data: bytes) -> None:
        raise NotImplementedError

    def get_bytes(self, key: str) -> bytes | None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError


class InMemoryBinaryStore(BinaryStore):
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = max(ttl_seconds, 0)
        self._lock = Lock()
        self._items: dict[str, tuple[bytearray, float | None]] = {}

    def append_bytes(self, key: str, data: bytes) -> None:
        if not data:
            return

        with self._lock:
            self._purge_expired_locked(key)
            buffer, _ = self._items.get(key, (bytearray(), None))
            buffer.extend(data)
            self._items[key] = (buffer, self._next_expiry())

    def set_bytes(self, key: str, data: bytes) -> None:
        with self._lock:
            self._items[key] = (bytearray(data), self._next_expiry())

    def get_bytes(self, key: str) -> bytes | None:
        with self._lock:
            self._purge_expired_locked(key)
            item = self._items.get(key)
            if not item:
                return None
            return bytes(item[0])

    def delete(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)

    def _next_expiry(self) -> float | None:
        if self.ttl_seconds <= 0:
            return None
        return time.time() + self.ttl_seconds

    def _purge_expired_locked(self, key: str) -> None:
        item = self._items.get(key)
        if not item:
            return

        _, expires_at = item
        if expires_at is not None and expires_at <= time.time():
            self._items.pop(key, None)


class RedisBinaryStore(BinaryStore):
    def __init__(self, url: str, key_prefix: str, ttl_seconds: int) -> None:
        if redis is None:
            raise BinaryStoreError(
                "REDIS_URL is configured, but the 'redis' package is not installed in this environment."
            )

        self.client = redis.Redis.from_url(url, decode_responses=False)
        self.key_prefix = key_prefix.strip() or "audioedit"
        self.ttl_seconds = max(ttl_seconds, 0)

        try:
            self.client.ping()
        except RedisError as exc:
            raise BinaryStoreError(f"Failed to connect to Redis: {exc}") from exc

    def append_bytes(self, key: str, data: bytes) -> None:
        if not data:
            return

        namespaced_key = self._key(key)
        try:
            self.client.append(namespaced_key, data)
            self._refresh_expiry(namespaced_key)
        except RedisError as exc:
            raise BinaryStoreError(f"Failed to append binary data to Redis: {exc}") from exc

    def set_bytes(self, key: str, data: bytes) -> None:
        namespaced_key = self._key(key)
        try:
            if self.ttl_seconds > 0:
                self.client.set(namespaced_key, data, ex=self.ttl_seconds)
            else:
                self.client.set(namespaced_key, data)
        except RedisError as exc:
            raise BinaryStoreError(f"Failed to store binary data in Redis: {exc}") from exc

    def get_bytes(self, key: str) -> bytes | None:
        namespaced_key = self._key(key)
        try:
            value = self.client.get(namespaced_key)
        except RedisError as exc:
            raise BinaryStoreError(f"Failed to read binary data from Redis: {exc}") from exc

        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        return bytes(value)

    def delete(self, key: str) -> None:
        namespaced_key = self._key(key)
        try:
            self.client.delete(namespaced_key)
        except RedisError as exc:
            raise BinaryStoreError(f"Failed to delete binary data from Redis: {exc}") from exc

    def _key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def _refresh_expiry(self, key: str) -> None:
        if self.ttl_seconds <= 0:
            return
        self.client.expire(key, self.ttl_seconds)


def build_binary_store(settings: Settings) -> BinaryStore:
    if settings.redis_url.strip():
        return RedisBinaryStore(
            url=settings.redis_url,
            key_prefix=settings.binary_key_prefix,
            ttl_seconds=settings.binary_ttl_seconds,
        )
    return InMemoryBinaryStore(ttl_seconds=settings.binary_ttl_seconds)
