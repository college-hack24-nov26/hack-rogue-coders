"""Optional Redis reads and private browser validation for selected GET routes."""
import hashlib
import json
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from fastapi.responses import JSONResponse, Response
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from .config import settings

MAX_VALUE_BYTES = 8 * 1024 * 1024


@lru_cache(maxsize=2)
def redis_client(url: str) -> Redis:
    return Redis.from_url(url, socket_connect_timeout=0.25, socket_timeout=0.25,
                          retry=Retry(NoBackoff(), 0), max_connections=16, protocol=2)


def cached_directory_rows(namespace: str, filters: tuple, load: Callable[[], list[dict]]) -> list[dict]:
    if not settings.redis_url:
        return load()

    # Separate deployments that share Redis and never include credentials in key text.
    scope = json.dumps([settings.database_url, settings.environment, filters], separators=(',', ':'))
    key = f'jalsathi:v1:{namespace}:{hashlib.sha256(scope.encode()).hexdigest()}'
    try:
        client = redis_client(settings.redis_url)
        cached = client.get(key)
    except (RedisError, OSError, ValueError):
        return load()
    if cached is not None and len(cached) <= MAX_VALUE_BYTES:
        try:
            rows = json.loads(cached)
            if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
                return rows
        except (ValueError, UnicodeError):
            pass

    rows = load()
    try:
        encoded = json.dumps(rows, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
        if len(encoded) <= MAX_VALUE_BYTES:
            client.set(key, encoded, ex=settings.redis_directory_ttl_seconds)
    except (RedisError, OSError, ValueError, TypeError):
        pass
    return rows


def browser_json(content: Any, if_none_match: str | None) -> Response:
    response = JSONResponse(content)
    etag = '"' + hashlib.sha256(response.body).hexdigest() + '"'
    headers = {'Cache-Control': 'private, no-cache', 'ETag': etag, 'Vary': 'Authorization'}
    if if_none_match:
        tags = [tag.strip().removeprefix('W/') for tag in if_none_match.split(',')]
        if etag in tags or tags == ['*']:
            return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return response
