# Deployment Information

## Public URL
- Public URL: `https://production-ai-agent-k5.up.railway.app` (hoặc `https://production-ai-agent-k5.onrender.com`)

## Platform
- Nền tảng: Railway / Render
- Source: `06-lab-complete/` (chạy image Docker build từ `Dockerfile` multi-stage)
- Managed Services: Cloud Redis (Redis URL kết nối nội bộ / public SSL)

## Environment Variables Set Trên Platform
- `PORT`: do platform cấp động (mặc định fallback 8000)
- `ENVIRONMENT`: `production`
- `AGENT_API_KEY`: `<set_via_platform_secret>`
- `REDIS_URL`: `redis://default:<password>@<host>:<port>` (kết nối Redis instance)
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
