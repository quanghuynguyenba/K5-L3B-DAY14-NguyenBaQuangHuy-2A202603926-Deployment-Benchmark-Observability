"""
Cost guard (tiêu chí 8).
"""
import time
from fastapi import HTTPException
from app.config import settings
from app.redis_client import get_redis_client

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

_memory_costs: dict[str, float] = {}


def check_budget(key: str = "") -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    budget = settings.daily_budget_usd
    day = time.strftime("%Y-%m-%d")
    cost_key = f"cost:{key}:{day}" if key else f"cost:daily:{day}"

    r = get_redis_client()
    current_cost = 0.0
    if r is not None:
        try:
            val = r.get(cost_key)
            if val is not None:
                current_cost = float(val)
        except Exception:
            current_cost = _memory_costs.get(cost_key, 0.0)
    else:
        current_cost = _memory_costs.get(cost_key, 0.0)

    if current_cost >= budget:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Budget exceeded",
                "current_cost_usd": current_cost,
                "budget_usd": budget,
            },
        )


def record_cost(input_tokens: int, output_tokens: int, key: str = "") -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    day = time.strftime("%Y-%m-%d")
    cost_key = f"cost:{key}:{day}" if key else f"cost:daily:{day}"

    r = get_redis_client()
    if r is not None:
        try:
            r.incrbyfloat(cost_key, cost)
            r.expire(cost_key, 86400 * 2)
            return cost
        except Exception:
            pass

    _memory_costs[cost_key] = _memory_costs.get(cost_key, 0.0) + cost
    return cost
