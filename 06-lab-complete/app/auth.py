"""
API Key authentication (tiêu chí 6).
"""
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Dependency cho FastAPI — dùng trong /ask: Depends(verify_api_key)."""
    expected_key = settings.agent_api_key
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include header: X-API-Key: <your-key>",
        )
    if api_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )
    return api_key
