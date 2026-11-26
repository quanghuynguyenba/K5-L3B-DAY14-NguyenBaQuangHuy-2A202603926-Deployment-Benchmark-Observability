# Benchmark & Observability Report — Day 14

> Mọi con số lấy từ report JSON / CSV thật trong thư mục `reports/` (đã chạy local qua `load_test.py` và `eval/run_eval.py`).

**Họ tên:** Nguyễn Bá Quang Huy  
**Mã sinh viên:** 2A202603926  
**Ngày chạy:** 26/11/2026  
**Môi trường:** Windows 11, Python 3.12, uvicorn async event loop (Localhost)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Đảm bảo trải nghiệm người dùng phản hồi nhanh, 95% request hoàn thành dưới 0.5s. |
| Error rate `/ask` | < 2.0 % | Chấp nhận tỷ lệ lỗi upstream ngẫu nhiên tối đa 2%, bảo vệ tính sẵn sàng của dịch vụ. |
| Accuracy trên golden dataset | ≥ 90.0 % | Đảm bảo chất lượng câu trả lời chuẩn xác của hệ thống RAG trước khi release. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.26 | 203.8 | 233.1 | 1713.9 | 1.67% | PASS |
| 10 | 36.84 | 188.6 | 235.4 | 1721.2 | 1.67% | PASS |
| 50 | 113.06 | 201.1 | 395.5 | 1723.0 | 0.33% | PASS |
| 100 | 53.70 | 559.4 | 3559.0 | 4255.4 | 0.00% | FAIL |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

- RPS **không** tăng tuyến tính vô hạn theo concurrency. Ở dải concurrency từ 1 đến 50, RPS tăng mạnh từ 4.26 lên đỉnh 113.06 req/s do event loop bất đồng bộ của FastAPI/uvicorn tận dụng tối đa thời gian chờ I/O của mock LLM.
- Tuy nhiên khi concurrency chạm ngưỡng 100, hệ thống rơi vào trạng thái bão hòa (saturation). CPU và event loop đơn luồng bị nghẽn hàng đợi (queueing delay), khiến latency p50 nhảy vọt lên 559.4ms và p95 lên tới 3559.0ms (> 500ms vi phạm SLO), kéo throughput tụt xuống còn 53.70 req/s.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 190.5 | 220.4 | 231.9 |
| 0.03 (mặc định) | 226.9 | 220.2 | 1708.6 |
| 0.1 | 328.6 | 1687.1 | 1725.1 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

- Chỉ số nhạy nhất với request chậm là **p99** và **p95** (khi tỷ lệ chậm tăng lên 10%). Khi `MOCK_SLOW_RATE` tăng từ 0 lên 0.03 (chỉ 3% request bị chậm), độ trễ trung bình `avg` chỉ tăng nhẹ từ 190.5ms lên 226.9ms (+36ms), nhưng `p99` đã nhảy vọt từ 231.9ms lên 1708.6ms (+1476ms).
- **Vì sao SLO không nên đặt theo average:**
  Giá trị trung bình che giấu hoàn toàn các spike bất thường (tail latency). Nếu chỉ nhìn con số 226ms, ta lầm tưởng hệ thống hoạt động rất mượt, trong khi thực tế cứ 100 người dùng thì có 1 đến 3 người phải chờ gần 2 giây. Đặt SLO theo p95/p99 đảm bảo cam kết chất lượng dịch vụ hướng tới trải nghiệm thực tế của người dùng.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% | 91.3% | 100.0% |
| Avg tokens / câu | 57.3 | 108.8 | 112.8 |
| Tổng cost (USD) | $0.000407 | $0.000758 | $0.000783 |
| Cost / câu đúng (USD) | $0.00040695 | $0.00003607 | $0.00003406 |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm tài liệu vào `KNOWLEDGE_BASE`: `"JWT là token có chữ ký số và thời gian hết hạn (expiry), mang thông tin người dùng mà không cần truy vấn database mỗi lần, khác với API key cố định."` |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm tài liệu vào `KNOWLEDGE_BASE`: `"Kubernetes HPA tự động scale số lượng pod dựa trên chỉ số CPU, memory hoặc custom metrics do ứng dụng cung cấp."` |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

- **Chất lượng:** Agent v2 vượt trội hoàn toàn nhờ có cơ chế Retrieval (RAG) tra cứu tài liệu trước khi trả lời, đưa độ chính xác từ 4.3% (gần như đoán mò) lên 91.3% và đạt 100% sau khi cập nhật knowledge base.
- **Chi phí:** Tổng cost của v2 ($0.000783) cao gần gấp đôi v1 ($0.000407) do prompt dài hơn khi đính kèm context. Tuy nhiên, nếu xét chỉ số **Cost / câu đúng**, v2 lại rẻ hơn v1 tới gần **12 lần** ($0.00003406 so với $0.00040695). Trả lời rẻ mà sai thì chi phí đó là vô ích; chi phí trên mỗi câu trả lời đúng mới là thước đo kinh tế thực tế.
- **Latency:** v2 chậm hơn v1 khoảng 20–30ms do tốn thêm thời gian search knowledge base (mô phỏng vector search), nhưng hoàn toàn nằm trong giới hạn cho phép (< 220ms).

### Cơ chế Quality Gate chặn Deploy trong CI/CD:
Script `eval/run_eval.py` trả về `exit code 0` khi đạt ngưỡng chất lượng và `exit code 1` khi accuracy < `--min-accuracy` hoặc phát hiện regression so với baseline. Trong pipeline CI/CD (GitHub Actions), bước kiểm tra được cấu hình:

```yaml
- name: Quality Gate Eval
  run: |
    python eval/run_eval.py --url http://localhost:8002 \
      --min-accuracy 1.0 \
      --baseline reports/eval_v2.json \
      --out reports/eval_v2_fixed.json
```
Nếu chất lượng bị giảm sút hoặc không đạt trần 100%, lệnh trả exit code 1 sẽ lập tức dừng pipeline và chặn hành động merge Pull Request.

---

## 4. Observability stack (production)

*(Phần này làm trong Part 7 Bước 2 — Exercise 7.4–7.7)*

### 4.1 Screenshot
- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals): `screenshots/grafana-dashboard.png`
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian): `screenshots/jaeger-slow-trace.png`
- [x] Một trace lỗi trong Jaeger (có event `exception`): `screenshots/jaeger-error-trace.png`
- [x] Trang Alerts của Prometheus với ít nhất 2 alert cùng firing: `screenshots/prometheus-alert-firing.png`

### 4.2 Thí nghiệm "phá hệ thống"
| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~1 phút (`for: 1m`) | Error rate & Requests/s theo status code (503) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | ~2 phút (`for: 2m`) | Latency /ask — p50 / p95 / p99 |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | ~2 phút (`for: 2m`) | Cost burn rate (USD/giờ) |
| D | `docker pause` 1 instance | `AgentInstanceDown` | ~30 giây (`for: 30s`) | Instances running (giảm từ 2 xuống 1) |
| E | `AGENT_VERSION=v1` | Không có alert nào firing | Không firing | Traffic & latency bình thường (chỉ giảm accuracy) |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**
Thí nghiệm E đổi sang `AGENT_VERSION=v1` làm chất lượng câu trả lời bị suy giảm nghiêm trọng (từ 100% xuống 4.3%), nhưng hệ thống hạ tầng vẫn phục vụ HTTP 200 rất nhanh và không hề có lỗi kết nối. Để phát hiện loại sự cố suy giảm chất lượng này, ta cần:
1. **Chạy Synthetic Eval định kỳ (Continuous Evals)**: Thiết lập một cron job tự động gọi agent với bộ golden dataset mỗi giờ để theo dõi accuracy theo thời gian.
2. **User Feedback Tracking**: Thu thập metrics từ nút Like/Dislike (thumbs up/down) của người dùng trên UI, tạo custom metric `user_dislike_ratio` và cấu hình alert khi tỷ lệ dislike tăng đột biến.
3. **LLM-as-a-Judge Online Sampling**: Lấy mẫu ngẫu nhiên 5% request production đưa qua một LLM giám sát (evaluator) để chấm điểm độ liên quan và tính chính xác của câu trả lời.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `4ca5f14de3ab9d2ef16bfcaef311690f`
- Tổng thời gian: `1688.1 ms` (~1.7 s)
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (~1667 ms, chiếm ~98.7% tổng thời gian; trong khi `agent.retrieve_context` chỉ mất `20.8 ms`)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-26T15:43:02.870729+00:00", "level": "INFO", "service": "observable-agent", "instance": "b7fb8febbaf2", "event": "http_request", "trace_id": "4ca5f14de3ab9d2ef16bfcaef311690f", "span_id": "ab325047c79206cc", "request_id": "deb76c38bfcf", "method": "POST", "route": "/ask", "status": 200, "ms": 1688.1}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

*(Số liệu tổng hợp từ `benchmark-results/scale_1_stats.csv` và `benchmark-results/scale_3_stats.csv`)*

| Số instance | RPS (Aggregated) | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 65.71 | 190 | 230 | 1700 | 72 (0.91%) |
| 3 | 65.77 | 190 | 230 | 1700 | 65 (0.83%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?
- Trong kịch bản Locust 100 users với `wait_time = between(0.5, 2)` giây, tổng lượng request sinh ra thực tế chỉ ở mức ~65.7 req/s.
- Vì agent sử dụng FastAPI bất đồng bộ (async event loop) và công việc chính của mock LLM là chờ I/O (`asyncio.sleep`), **chỉ riêng 1 instance đã đủ sức xử lý mức tải 65.7 req/s** mà chưa chạm ngưỡng bão hòa CPU. Do đó, việc scale lên 3 instances không làm giảm thêm p50 (190ms) hay p95 (230ms).
- Nút thắt (bottleneck) lúc này nằm ở **tốc độ sinh tải tối đa của Locust (bị giới hạn bởi `wait_time`)** và **upstream LLM latency** (3% slow request mất ~1.7s khiến p99 giữ nguyên ở 1700ms dù chạy 1 hay 3 instance). Horizontal scaling chỉ giúp cải thiện p95 rõ rệt khi mức tải đồng thời vượt ngưỡng bão hòa của 1 container.

---

## 6. Kết luận

- **3 điều học được về benchmark & observability:**
  1. **Đo bằng percentile (`p95`/`p99`) thay vì trung bình (`avg`):** Giá trị trung bình che giấu các spike bất thường (tail latency), trong khi p95/p99 phản ánh sát nhất trải nghiệm của nhóm người dùng gặp độ trễ cao.
  2. **Chất lượng & Kinh tế đi kèm Quality Gate:** Chi phí thực tế của AI agent phải đánh giá trên **cost / câu trả lời đúng** chứ không phải cost / request; đồng thời bắt buộc phải có Eval Quality Gate trong CI vì hệ thống giám sát hạ tầng (Prometheus/Grafana) không thể tự phát hiện lỗi suy giảm chất lượng câu trả lời.
  3. **Sức mạnh của 3 trụ cột Observability:** Metrics (Prometheus + Grafana) giúp phát hiện nhanh bất thường qua Golden Signals và Alerting; Traces (Jaeger) khoanh vùng chính xác span gây chậm/lỗi; Structured JSON Logs gắn `trace_id` kết nối trực tiếp log với trace để debug nhanh chóng.
- **Nếu đưa agent này lên production thật, sẽ thêm metric / alert nào nữa:**
  - **Continuous Eval & User Feedback Metrics:** Metric `agent_eval_accuracy` chạy định kỳ trên tập golden dataset và `user_dislike_ratio` từ phản hồi người dùng, kèm alert nếu chất lượng tụt dưới ngưỡng SLO.
  - **Budget & Rate Limit Alerts:** Alert `DailyBudgetNearLimit` (khi chi tiêu vượt 85% `DAILY_BUDGET_USD`) và `HighRateLimit429Rate` (khi tỷ lệ HTTP 429 tăng đột biến) để kịp thời phát hiện tấn công lạm dụng API hoặc rò rỉ key.
