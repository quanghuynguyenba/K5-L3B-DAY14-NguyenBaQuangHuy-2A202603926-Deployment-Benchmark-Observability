# Deployment Information

## Public URL
- Public URL: `https://production-ai-agent-83m0.onrender.com`

## Platform
- Nền tảng: Render
- Source: `06-lab-complete/` (chạy image Docker build từ `Dockerfile` multi-stage)
- Managed Services: Render Redis (`agent-redis`, Internal Connection String)

## Environment Variables Set Trên Platform
- `PORT`: 8000 (Render cấp)
- `ENVIRONMENT`: `production`
- `AGENT_API_KEY`: Đã cấu hình trên Render Environment
- `REDIS_URL`: `redis://red-dc440uijnfac73bf0ne0:<REDACTED_PASSWORD>@red-dc440uijnfac73bf0ne0:6379` (Internal Connection String trên Render)
- `RATE_LIMIT_PER_MINUTE`: `60`
- `DAILY_BUDGET_USD`: `10.0`

## Test Commands (4 Lệnh Tự Kiểm CP6)

Chạy với `$BASE` là URL public của service và `$AGENT_API_KEY` là key đã cấu hình:

```bash
# 1. Health check — liveness (Kỳ vọng: 200)
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"

# 2. Readiness check — kiểm tra kết nối Redis (Kỳ vọng: 200)
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"

# 3. Request không có API Key (Kỳ vọng: 401)
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'

# 4. Request có API Key hợp lệ (Kỳ vọng: 200)
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
```

## Screenshots
- Dashboard: [screenshots/dashboard.png](screenshots/dashboard.png)
- Service running: [screenshots/running.png](screenshots/running.png)
- 4 test commands: [screenshots/test.png](screenshots/test.png)
