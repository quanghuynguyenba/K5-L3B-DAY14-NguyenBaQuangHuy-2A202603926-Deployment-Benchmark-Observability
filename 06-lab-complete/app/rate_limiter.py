"""
Rate limiting (tiêu chí 7).
"""
import time
import uuid
from collections import defaultdict, deque
from fastapi import HTTPException
from app.config import settings
from app.redis_client import get_redis_client

_memory_windows: dict[str, deque] = defaultdict(deque)


def check_rate_limit(key: str) -> None:
    limit = settings.rate_limit_per_minute
    window = 60.0
    now = time.time()
    r = get_redis_client()

    if r is not None:
        redis_key = f"ratelimit:{key}"
        try:
            pipe = r.pipeline()
            pipe.zremrangebyscore(redis_key, 0, now - window)
            pipe.zcard(redis_key)
            pipe.zrange(redis_key, 0, 0, withscores=True)
            results = pipe.execute()
            count = results[1]
            oldest = results[2]

            if count >= limit:
                oldest_ts = oldest[0][1] if oldest else (now - window)
                retry_after = max(1, int(oldest_ts + window - now) + 1)
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(retry_after)},
                )

            pipe = r.pipeline()
            member = f"{now}-{uuid.uuid4().hex[:6]}"
            pipe.zadd(redis_key, {member: now})
            pipe.expire(redis_key, int(window) + 5)
            pipe.execute()
            return
        except HTTPException:
            raise
        except Exception:
            pass

    # In-memory fallback
    dq = _memory_windows[key]
    while dq and dq[0] < now - window:
        dq.popleft()

    if len(dq) >= limit:
        oldest = dq[0]
        retry_after = max(1, int(oldest + window - now) + 1)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    dq.append(now)
