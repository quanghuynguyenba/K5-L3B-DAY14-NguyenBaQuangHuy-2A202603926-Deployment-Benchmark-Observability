"""
Config — 12-Factor: mọi cấu hình đọc từ biến môi trường.
"""
import os
from dataclasses import dataclass


@dataclass
class Settings:
    @property
    def port(self) -> int:
        return int(os.getenv("PORT", "8000"))

    @property
    def environment(self) -> str:
        return os.getenv("ENVIRONMENT", "development")

    @property
    def agent_api_key(self) -> str:
        return os.getenv("AGENT_API_KEY", "")

    @property
    def redis_url(self) -> str:
        return os.getenv("REDIS_URL", "")

    @property
    def rate_limit_per_minute(self) -> int:
        return int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

    @property
    def daily_budget_usd(self) -> float:
        val = os.getenv("DAILY_BUDGET_USD") or os.getenv("MONTHLY_BUDGET_USD")
        return float(val) if val else 1.0


settings = Settings()
