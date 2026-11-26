# Mission Answers

## Part 2 — Docker

### Exercise 2.1: Dockerfile cơ bản

1. Base image: `python:3.11`.
2. Working directory trong container: `/app`.
3. `requirements.txt` được copy trước source code để Docker có thể tái sử dụng layer cài dependencies khi chỉ source code thay đổi.
4. `CMD` đặt lệnh hoặc tham số mặc định khi container khởi động và có thể được ghi đè lúc chạy. `ENTRYPOINT` định nghĩa chương trình chính; `CMD` thường cung cấp tham số mặc định cho chương trình đó.

### Exercise 2.2: Build và run

Build từ thư mục gốc repository:

```powershell
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -p 8000:8000 my-agent:develop
```

Container chạy thành công. Gọi `POST /ask?question=What%20is%20Docker` trả về:

```json
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

Health check trả HTTP 200 với trạng thái `ok` và `container: true`.

### Exercise 2.3: Multi-stage build

- Stage 1 (`builder`) cài build tools và Python dependencies.
- Stage 2 (`runtime`) dùng `python:3.11-slim`, chỉ chép các packages và source cần thiết để chạy app; app chạy bằng user không phải root.
- Multi-stage build giảm kích thước image runtime vì không mang theo compiler và build tools.

Đo bằng `docker image inspect`:

| Image | Kích thước Docker CLI | Kích thước bytes |
|---|---:|---:|
| `my-agent:develop` | 1.67 GB | 1,667,792,263 |
| `my-agent:advanced` | 240 MB | 239,815,386 |

Image production nhỏ hơn khoảng **85.62%** so với image develop.

### Exercise 2.4: Docker Compose stack

Các service và luồng giao tiếp:

```text
Client → Nginx (host ports 80/443) → Agent
                                      ├→ Redis (session/cache)
                                      └→ Qdrant (vector database)
```

Compose khởi động `nginx`, `agent`, `redis` và `qdrant` trên network nội bộ. Redis và Qdrant dùng named volumes để lưu dữ liệu; Agent chỉ được truy cập từ ngoài thông qua Nginx.

Kết quả kiểm tra qua Nginx:

- `GET /health`: HTTP 200.
- `GET /ready`: HTTP 200.
- `POST /ask` với JSON body `{"question":"Explain microservices"}`: HTTP 200.

Lưu ý: bản production nhận câu hỏi trong JSON body; không gửi `question` dưới dạng query string như bản develop.

## Part 3 — Cloud Deployment

### Exercise 3.1 & 3.2: Triển khai Agent Part 6 và So sánh nền tảng

- **URL Public:** `https://production-ai-agent-k5.up.railway.app` (hoặc `https://production-ai-agent-k5.onrender.com`)
- **Ảnh minh chứng:** Lưu tại [screenshots/](screenshots/) (`dashboard.png`, `running.png`, `test.png`).
- **Kết quả 4 lệnh tự kiểm tra CP6:**
  1. `GET /health` → HTTP 200 (Liveness OK).
  2. `GET /ready` → HTTP 200 (Đã kết nối Redis).
  3. `POST /ask` (không có key) → HTTP 401 Unauthorized.
  4. `POST /ask` (kèm header `X-API-Key: $AGENT_API_KEY`) → HTTP 200 OK.

#### So sánh cấu hình `railway.toml` và `render.yaml` (Khác nhau & Lý do):

| Tiêu chí | `railway.toml` (Railway) | `render.yaml` (Render Blueprint) |
|---|---|---|
| **Định dạng file** | TOML — ngắn gọn, tập trung vào cấu hình runtime và build pipeline của từng service riêng lẻ. | YAML — chuẩn Blueprint Infrastructure-as-Code (IaC), cho phép khai báo toàn bộ hệ sinh thái (web, database, worker, cron) trong một file duy nhất. |
| **Khai báo Builder** | Sử dụng khối `[build]` với `builder = "DOCKERFILE"` (hoặc Nixpacks), tự động quét Dockerfile trong thư mục triển khai. | Sử dụng danh sách `services:`, định nghĩa rõ `type: web` và `runtime: docker`. |
| **Quản lý Cổng (Port)** | Không cần cấu hình cổng cố định; Railway tự động inject biến môi trường `$PORT` ngẫu nhiên và route traffic qua domain public. Lệnh chạy trong container cần dùng `${PORT:-8000}`. | Cho phép chỉ định biến môi trường `PORT: 8000` hoặc tự nhận diện cổng container đã EXPOSE. |
| **Health Check Path** | Thuộc tính `healthcheckPath = "/health"` trong block `[deploy]`, hỗ trợ cấu hình `restartPolicyType` và timeout. | Thuộc tính `healthCheckPath: /health` nằm trực tiếp trong định nghĩa service. |
| **Quản lý Secrets & Biến môi trường** | Thường không lưu secret trực tiếp trong `railway.toml` mà thiết lập qua Dashboard hoặc Railway CLI (`railway variables set`). | Hỗ trợ quản lý declarative với trường `envVars`: các secret như `AGENT_API_KEY` được bảo vệ tuyệt đối bằng cú pháp `generateValue: true` (tự tạo secret ngẫu nhiên) hoặc `sync: false` (yêu cầu điền thủ công trên dashboard), ngăn chặn hoàn toàn việc lộ secret vào git. |

### Exercise 3.3: Google Cloud Build CI/CD Pipeline (`cloudbuild.yaml` & `service.yaml`)

Pipeline CI/CD trong `03-cloud-deployment/production-cloud-run/` tự động kích hoạt khi có commit mới được push vào nhánh `main` và thực thi qua 4 bước:

1. **Step 1 — Chạy Automated Tests (`python:3.11-slim`)**: Môi trường container cài đặt dependencies và thực thi pytest (`pytest tests/ -v`). Nếu bất kỳ test nào fail, pipeline lập tức dừng lại để bảo vệ production khỏi regression.
2. **Step 2 — Đóng gói Container Image (`docker build`)**: Docker build agent image với 2 tag: commit SHA cụ thể (`$COMMIT_SHA`) và `latest`. Pipeline sử dụng cờ `--cache-from=gcr.io/$PROJECT_ID/ai-agent:latest` để tái sử dụng các layer không đổi từ lần build trước, giúp giảm tối đa thời gian build.
3. **Step 3 — Push Image lên Registry (`docker push`)**: Đẩy toàn bộ các tag của image vừa build lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **Step 4 — Triển khai lên Google Cloud Run (`gcloud run deploy`)**:
   - Triển khai phiên bản image `$COMMIT_SHA` lên Cloud Run dạng fully-managed tại region `asia-southeast1` với cờ `--allow-unauthenticated` để mở public endpoint.
   - Cấu hình hạ tầng: cấp phát 1 CPU, 512Mi RAM, concurrency tối đa 80 requests/container, timeout 60s.
   - Cơ chế Autoscaling: `min-instances=1` (giữ ít nhất 1 container luôn chạy để triệt tiêu hoàn toàn độ trễ Cold Start cho AI agent) và `max-instances=10` để kiểm soát trần chi phí.
   - Quản lý Secret: Sử dụng `--set-secrets` trỏ tới Google Secret Manager (`OPENAI_API_KEY=openai-key:latest`, `AGENT_API_KEY=agent-api-key:latest`) thay vì truyền qua biến môi trường thông thường, đảm bảo chuẩn bảo mật cấp doanh nghiệp.
   - Cơ chế Probe (trong `service.yaml`): Thiết lập `livenessProbe` gọi `/health` (chu kỳ 30s) để tự phục hồi khi crash và `startupProbe` gọi `/ready` (chu kỳ 3s, tối đa 10 lần) để đảm bảo container chỉ nhận traffic khi đã sẵn sàng.

## Part 4 — API Security

### Exercise 4.1: API key authentication

`AGENT_API_KEY` được đọc từ biến môi trường. Dependency `verify_api_key` bảo vệ `POST /ask`: thiếu key trả HTTP 401, key không hợp lệ trả HTTP 403, key đúng cho phép request tiếp tục. Có thể rotate key bằng cách đổi biến môi trường rồi khởi động lại app; không ghi key thật vào source code.

Đã nhận response body khi gọi thiếu key:

```json
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

Chưa lưu lại status line và headers từ `curl -i`; chạy lại test để chụp đủ bằng chứng HTTP 401. Output gọi thành công bằng API key: **chưa ghi nhận**.

### Exercise 4.2: JWT authentication

Lấy JWT bằng `POST /auth/token` với demo user `student` / `demo123`. Token hết hạn sau 60 phút; request được bảo vệ gửi token trong header `Authorization: Bearer <token>`. Không dán token vào báo cáo.

Token đã được lấy thành công. Output `curl -i` của request `/ask` có JWT (HTTP 200): **chưa ghi nhận**.

### Exercise 4.3: Rate limiting

User tier bị giới hạn **10 request trong 60 giây**; admin tier là **100 request trong 60 giây**. Mã nguồn mô tả thuật toán là Sliding Window Counter và thực tế lưu timestamp từng request trong `deque`, loại bỏ timestamp cũ hơn cửa sổ 60 giây. Khi vượt giới hạn, API trả HTTP 429 cùng thông tin giới hạn và `Retry-After`.

Output thực tế `curl -i` khi vượt giới hạn (HTTP 429): **chưa ghi nhận**.

### Exercise 4.4: Cost guard và so sánh với hướng Redis

Code production hiện tại là **demo in-memory, ngân sách theo ngày**: mặc định `$1/ngày` cho mỗi user và `$10/ngày` toàn hệ thống. `check_budget()` kiểm tra mức đã dùng trước khi gọi mock LLM; `record_usage()` ước tính chi phí từ số token input/output rồi cộng vào bộ đếm; `get_usage()` trả thống kê. Có cảnh báo ở mức 80%. Dữ liệu mất khi tiến trình khởi động lại và không chia sẻ giữa nhiều worker. User record được làm mới theo ngày; bộ đếm toàn cục hiện không tự reset theo ngày.

Khác với code hiện tại, bài tập trong `CODE_LAB.md` hướng tới phiên bản bền vững hơn: lưu spending trong Redis với key theo user và tháng, giới hạn `$10/user/tháng`, rồi cập nhật chi phí và đặt thời hạn cho key. Đây là hướng bài tập, không phải implementation hiện tại trong `cost_guard.py`.

Rate limiting giới hạn **tốc độ/tần suất** gọi để giảm spam hoặc quá tải; cost guard giới hạn **tổng chi phí** để tránh vượt ngân sách. Chỉ rate limit không ngăn được chi phí cao từ request đắt; chỉ cost guard không ngăn được burst request hoặc quá tải trước khi chạm ngân sách, nên cần cả hai.

## Part 5 — Scaling & Reliability

### Exercises 5.1–5.2: Health checks và graceful shutdown

Chạy bản `05-scaling-reliability/develop` trên cổng 8001 để tránh xung đột với app khác đang dùng cổng 8000. Cả ba endpoint trả HTTP 200 sau startup:

- `GET /health`: `{"status":"ok", ...}` — liveness, cho biết process còn sống.
- `GET /ready`: `{"ready":true, ...}` — readiness, cho biết app đã sẵn sàng nhận traffic.
- `POST /ask?question=hello`: trả câu trả lời mock thành công.

Khi dừng stack production bằng `docker compose stop`, cả ba agent nhận tín hiệu dừng; log cho thấy `Shutting down`, lifecycle shutdown của từng instance, rồi `Application shutdown complete`. Như vậy container dừng có trật tự thay vì bị kill cưỡng bức.

### Exercises 5.3–5.5: Stateless sessions và load balancing

Stack được chạy bằng:

```bash
docker compose -p k5-day14-scaling -f 05-scaling-reliability/production/docker-compose.yml up -d --build --scale agent=3
```

Compose có ba agent instances, Redis và Nginx (host port 8080). Log agent xác nhận `Storage: Redis`.

`python test_stateless.py` hoàn thành 5 request liên tiếp cho cùng một session. Các request được xử lý bởi ba instance khác nhau (`instance-63541c`, `instance-5c41fb`, `instance-46a9a1`); đọc history sau đó trả về đủ **10 messages** (5 câu hỏi và 5 câu trả lời). Điều này xác nhận session được chia sẻ qua Redis thay vì chỉ lưu trong memory của một instance.

Lưu ý: script `test_stateless.py` hiện tại xác minh session continuity và phân phối request; nó **không** tự kill instance. Stack đã được dừng sau khi kiểm thử bằng `docker compose -p k5-day14-scaling -f 05-scaling-reliability/production/docker-compose.yml down`.

## Part 6 — Final Project (Production-ready AI Agent)

### Checklist Deliverable

```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 42/42 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

### Chi tiết hoàn thành 12 tiêu chí trong `06-lab-complete/`:

1. **Dockerfile:** Multi-stage build (`builder` và `runtime` trên nền `python:3.11-slim`), non-root user `appuser` (UID 1000), có `HEALTHCHECK` gọi `/health`, dung lượng image **273 MB** (< 500 MB). Lệnh khởi chạy `CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]` đảm bảo uvicorn là PID 1 để đón nhận tín hiệu shutdown.
2. **docker-compose.yml:** Khởi chạy `agent` (build từ `Dockerfile`) và `redis` (`redis:7-alpine`). Service `agent` phụ thuộc vào `redis` (`depends_on`) và nhận `REDIS_URL=redis://redis:6379/0`.
3. **.dockerignore:** Loại bỏ triệt để `.git`, cache Python (`__pycache__`, `*.pyc`), virtualenv (`venv`, `.venv`), secrets (`.env*` ngoại trừ `.env.example`), logs và thư mục benchmark.
4. **Health check (`GET /health`):** Luôn trả `{"status": "ok"}` HTTP 200 ngay cả khi Redis chưa sẵn sàng hoặc mất kết nối.
5. **Readiness endpoint (`GET /ready`):** Kiểm tra trạng thái ping Redis. Trả HTTP 200 khi Redis kết nối tốt và HTTP 503 khi Redis bị ngắt kết nối.
6. **API Key Authentication:** Middleware kiểm tra header `X-API-Key` khớp với biến môi trường `AGENT_API_KEY`. Thiếu hoặc sai key đều trả về HTTP 401.
7. **Rate Limiting:** Sử dụng thuật toán Sliding Window với Redis Sorted Sets (`zremrangebyscore`, `zcard`, `zadd`, `expire`), tự động chặn request vượt ngưỡng `RATE_LIMIT_PER_MINUTE` bằng HTTP 429 kèm header `Retry-After`. Trạng thái lưu trữ phân tán trong Redis giúp agent stateless (restart agent vẫn duy trì hạn mức).
8. **Cost Guard:** Ước tính chi phí theo token ($0.00015/1k input, $0.0006/1k output) và tích luỹ chi phí theo ngày trong Redis. Trả HTTP 402 Payment Required khi tổng chi phí vượt quá `DAILY_BUDGET_USD`.
9. **Environment Config:** Toàn bộ cấu hình (`PORT`, `ENVIRONMENT`, `AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`) được đọc động qua `os.getenv` trong `app/config.py`. File `.env.example` liệt kê đầy đủ các biến và `.env` được bảo vệ trong `.gitignore`.
10. **Structured Logging:** Sử dụng custom `JsonFormatter` kế thừa `logging.Formatter` kết hợp HTTP middleware ghi log toàn bộ request/response dưới dạng JSON object hợp lệ chứa timestamp UTC, log level, event, path, status, latency ms.
11. **Graceful Shutdown:** Quản lý vòng đời qua `lifespan` context manager của FastAPI. Uvicorn chạy PID 1 đón nhận `SIGTERM` khi dừng container, xử lý nốt các request đang bay và thoát êm trong 0.6s (< 10s) với exit code 0.
12. **Deploy Configuration:** Cung cấp đầy đủ cả `railway.toml` và `render.yaml` chuẩn production, hỗ trợ cấu hình biến `PORT` động từ platform và healthcheck endpoint `/health`.

