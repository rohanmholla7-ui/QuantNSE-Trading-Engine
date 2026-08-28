from __future__ import annotations

import json
from typing import Any

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None  # type: ignore


class StateStore:
    """Redis-backed JSON store with in-process fallback for tests/demo."""

    def __init__(self, url: str) -> None:
        self._mem: dict[str, str] = {}
        self._client = None
        if redis is not None:
            try:
                client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=0.4)
                client.ping()
                self._client = client
            except Exception:
                self._client = None

    @property
    def using_redis(self) -> bool:
        return self._client is not None

    def set_json(self, key: str, value: Any) -> None:
        payload = json.dumps(value, default=str)
        if self._client is not None:
            self._client.set(key, payload)
        else:
            self._mem[key] = payload

    def get_json(self, key: str, default: Any = None) -> Any:
        raw = None
        if self._client is not None:
            raw = self._client.get(key)
        else:
            raw = self._mem.get(key)
        if raw is None:
            return default
        return json.loads(raw)

    def set(self, key: str, value: str) -> None:
        if self._client is not None:
            self._client.set(key, value)
        else:
            self._mem[key] = value

    def get(self, key: str, default: str | None = None) -> str | None:
        if self._client is not None:
            val = self._client.get(key)
            return val if val is not None else default
        return self._mem.get(key, default)
