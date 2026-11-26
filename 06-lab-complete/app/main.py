"""
Production AI Agent — Part 6 Final Project
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy, redis_status
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        if msg.startswith("{") and msg.endswith("}"):
            try:
                json.loads(msg)
                return msg
            except Exception:
                pass
        log_obj = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": msg,
        }
        return json.dumps(log_obj, ensure_ascii=False)


# Cấu hình structured logging (tiêu chí 10)
log_handler = logging.StreamHandler(sys.stdout)
log_handler.setFormatter(JsonFormatter())
logging.root.handlers = [log_handler]
logging.root.setLevel(logging.INFO)

logger = logging.getLogger("app.main")


# Tiêu chí 11: Graceful shutdown qua lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(json.dumps({"event": "startup", "environment": settings.environment}))
    yield
    logger.info(json.dumps({"event": "shutdown", "status": "completed"}))


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)
    logger.info(
        json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": "INFO",
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration_ms,
        })
    )
    return response


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    ok, reason = redis_status()
    if not ok:
        raise HTTPException(
            status_code=503,
            detail={"status": "not ready", "redis": False, "reason": reason},
        )
    return {"status": "ready", "redis": True}


@app.post("/ask")
def ask(
    body: Optional[AskRequest] = None,
    question: Optional[str] = None,
    api_key: str = Depends(verify_api_key),
):
    q = (body.question if body else None) or question
    if not q:
        raise HTTPException(status_code=422, detail="Missing question")

    # Tiêu chí 7: Rate limit check (429 khi vượt giới hạn)
    check_rate_limit(api_key)

    # Tiêu chí 8: Cost guard check (402 khi hết budget)
    check_budget(api_key)

    # Gọi LLM
    answer = llm_ask(q)

    # Tính toán tokens và ghi nhận chi phí
    input_tokens = len(q.split()) * 2 + 10
    output_tokens = len(answer.split()) * 2 + 10
    record_cost(input_tokens, output_tokens, api_key)

    return {"question": q, "answer": answer}
