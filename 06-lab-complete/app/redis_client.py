"""
Kết nối Redis dùng chung cho rate limiter và cost guard.
"""
import logging
from typing import Optional
import redis
from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    global _redis_client
    url = settings.redis_url
    if not url:
        return None
    try:
        if _redis_client is None:
            _redis_client = redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
        return _redis_client
    except Exception as e:
        logger.warning(f"Failed to create Redis client: {e}")
        return None


def redis_status() -> tuple[bool, str]:
    url = settings.redis_url
    if not url:
        return False, "REDIS_URL is not set"
    try:
        client = redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=3.0,
            socket_timeout=3.0,
        )
        if bool(client.ping()):
            return True, "ok"
        return False, "ping returned False"
    except Exception as e:
        return False, str(e)


def redis_healthy() -> bool:
    return redis_status()[0]
