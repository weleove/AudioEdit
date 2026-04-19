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
    """二进制存储错误"""
    pass


class BinaryStore:
    """二进制存储抽象基类"""
    def append_bytes(self, key: str, data: bytes) -> None:
        """追加字节数据到指定键"""
        raise NotImplementedError

    def set_bytes(self, key: str, data: bytes) -> None:
        """设置键的字节数据（覆盖）"""
        raise NotImplementedError

    def get_bytes(self, key: str) -> bytes | None:
        """获取键的字节数据"""
        raise NotImplementedError

    def delete(self, key: str) -> None:
        """删除指定键"""
        raise NotImplementedError


class InMemoryBinaryStore(BinaryStore):
    """内存二进制存储实现（带 TTL 过期机制）"""
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = max(ttl_seconds, 0)  # 过期时间（秒）
        self._lock = Lock()  # 线程锁
        self._items: dict[str, tuple[bytearray, float | None]] = {}  # 存储字典：键 -> (数据, 过期时间)

    def append_bytes(self, key: str, data: bytes) -> None:
        """追加字节数据"""
        if not data:
            return

        with self._lock:
            self._purge_expired_locked(key)
            buffer, _ = self._items.get(key, (bytearray(), None))
            buffer.extend(data)
            self._items[key] = (buffer, self._next_expiry())

    def set_bytes(self, key: str, data: bytes) -> None:
        """设置字节数据"""
        with self._lock:
            self._items[key] = (bytearray(data), self._next_expiry())

    def get_bytes(self, key: str) -> bytes | None:
        """获取字节数据"""
        with self._lock:
            self._purge_expired_locked(key)
            item = self._items.get(key)
            if not item:
                return None
            return bytes(item[0])

    def delete(self, key: str) -> None:
        """删除键"""
        with self._lock:
            self._items.pop(key, None)

    def _next_expiry(self) -> float | None:
        """计算下次过期时间"""
        if self.ttl_seconds <= 0:
            return None
        return time.time() + self.ttl_seconds

    def _purge_expired_locked(self, key: str) -> None:
        """清理已过期的键（需持有锁）"""
        item = self._items.get(key)
        if not item:
            return

        _, expires_at = item
        if expires_at is not None and expires_at <= time.time():
            self._items.pop(key, None)


class RedisBinaryStore(BinaryStore):
    """Redis 二进制存储实现"""
    def __init__(self, url: str, key_prefix: str, ttl_seconds: int) -> None:
        if redis is None:
            raise BinaryStoreError(
                "REDIS_URL is configured, but the 'redis' package is not installed in this environment."
            )

        self.client = redis.Redis.from_url(url, decode_responses=False)  # Redis 客户端
        self.key_prefix = key_prefix.strip() or "audioedit"  # 键前缀
        self.ttl_seconds = max(ttl_seconds, 0)  # 过期时间

        try:
            self.client.ping()  # 测试连接
        except RedisError as exc:
            raise BinaryStoreError(f"Failed to connect to Redis: {exc}") from exc

    def append_bytes(self, key: str, data: bytes) -> None:
        """追加字节数据到 Redis"""
        if not data:
            return

        namespaced_key = self._key(key)
        try:
            self.client.append(namespaced_key, data)
            self._refresh_expiry(namespaced_key)
        except RedisError as exc:
            raise BinaryStoreError(f"Failed to append binary data to Redis: {exc}") from exc

    def set_bytes(self, key: str, data: bytes) -> None:
        """设置 Redis 键的字节数据"""
        namespaced_key = self._key(key)
        try:
            if self.ttl_seconds > 0:
                self.client.set(namespaced_key, data, ex=self.ttl_seconds)
            else:
                self.client.set(namespaced_key, data)
        except RedisError as exc:
            raise BinaryStoreError(f"Failed to store binary data in Redis: {exc}") from exc

    def get_bytes(self, key: str) -> bytes | None:
        """从 Redis 获取字节数据"""
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
        """从 Redis 删除键"""
        namespaced_key = self._key(key)
        try:
            self.client.delete(namespaced_key)
        except RedisError as exc:
            raise BinaryStoreError(f"Failed to delete binary data from Redis: {exc}") from exc

    def _key(self, key: str) -> str:
        """生成带命名空间的键"""
        return f"{self.key_prefix}:{key}"

    def _refresh_expiry(self, key: str) -> None:
        """刷新键的过期时间"""
        if self.ttl_seconds <= 0:
            return
        self.client.expire(key, self.ttl_seconds)


def build_binary_store(settings: Settings) -> BinaryStore:
    """根据配置构建二进制存储实例（Redis 或内存）"""
    if settings.redis_url.strip():
        return RedisBinaryStore(
            url=settings.redis_url,
            key_prefix=settings.binary_key_prefix,
            ttl_seconds=settings.binary_ttl_seconds,
        )
    return InMemoryBinaryStore(ttl_seconds=settings.binary_ttl_seconds)
