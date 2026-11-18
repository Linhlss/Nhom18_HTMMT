# Đặc tả workload request/response và cấu hình (N18-002)

| Mục | Nội dung |
|---|---|
| Task | **N18-002**, tuần 1 — Đặc tả workload request/response và cấu hình |
| Người phụ trách (DRI) | TV2 |
| Người review | TV3 (schema, cách ghi thời gian, khả năng dùng log để tính metric) |
| Phiên bản | **v1.0**, 18/11/2026. Thay bản nháp v0 `Workload Spec.pdf` (ngoài repo); thay đổi ở [§10](#10-thay-đổi-so-với-bản-nháp-v0) |
| Trạng thái | **Hoàn thành** — TV3 đã review (theo xác nhận của nhóm trưởng TV1 ngày 18/11/2026) |
| Mã nguồn | [`workload/`](../workload/), cấu hình mẫu [`workload/configs/`](../workload/configs/) |
| Minh chứng | [`evidence/tv2-week1/`](../evidence/tv2-week1/README.md) |
| Liên quan | [Đặc tả metric](metrics-spec.md), [Phạm vi & rubric](scope-rubric.md), [Bàn giao mạng TV1](network-handoff.md) |

> **Dữ liệu minh họa:** mọi giá trị trong ví dụ cấu hình/payload của tài liệu này chỉ minh họa cấu trúc, **không phải dữ liệu đo**. Chỉ các số ở [§8](#8-bài-thử-khởi-động-tuần-1) là dữ liệu đo thật, kèm lệnh chạy, môi trường, raw log và commit mã nguồn.

## 1. Phạm vi

Workload là **tải request/response giả lập** cho dịch vụ AI inference: client gửi yêu cầu có kích thước xác định, server emulator chờ một khoảng *service delay* rồi trả response có kích thước xác định. **Không chạy LLM/GPU/API thật.** Mục tiêu là sinh tải mạng có tham số kiểm soát được để đo và so sánh profile A/B; không tuyên bố là trace traffic của doanh nghiệp.

Ràng buộc từ hạ tầng TV1 ([network-handoff.md](network-handoff.md)): client `c1=10.18.1.10`, `c2=10.18.2.10`; server `a1=10.18.3.11`, `a2=10.18.3.12`; firewall chỉ mở TCP **8000** cho ứng dụng (và 5201–5208 cho iperf3). Profile B tách luồng **theo subnet client** (static OpenFlow flow-splitting, không phải ECMP), nên kết nối phải được phân luân phiên c1, c2.

**Phạm vi phiên bản v1 (đã chốt):** giao thức **`tcp-binary-v1`** — TCP, framing nhị phân, cổng 8000. **HTTP là phần mở rộng tương lai**, chưa được đặc tả và validator sẽ từ chối `protocol: "http"`.

## 2. Định danh và thời gian (thống nhất với TV3)

| Khái niệm | Định nghĩa | Ví dụ (minh họa) |
|---|---|---|
| `run_id` | Định danh **một lượt chạy**. Định dạng `<UTC YYYYMMDDTHHMMSSffffffZ>-<label>`, trùng tên thư mục evidence | `20261118T112728069663Z-tv2-smoke` |
| `config_id` | Định danh **cấu hình workload** (size/rate/concurrency/delay…). `^[a-z0-9][a-z0-9_.-]{0,63}$`. Đổi bất kỳ tham số workload nào thì tăng hậu tố `_vN` | `smoke_c1_a1_v1` |
| `profile` | Cấu hình **mạng** A/B do `networkctl status` báo tại lúc chạy. **Không** gộp vào `config_id`; cùng `config_id` chạy trên A và B mới là cặp đối chứng | `A` |
| `config_sha256` | SHA-256 của file cấu hình đã dùng, ghi trong `client-summary.json` | — |
| `req_id` | `{run_id}_f{flow_id}_r{seq}` | `…-tv2-smoke_f0_r3` |

**Thời gian:**

- `*_utc`: ISO-8601 UTC độ phân giải micro giây, đuôi `Z`. Chỉ dùng để **đối chiếu log** giữa các nguồn (client, server, ping, counter).
- `*_mono_ns`: `time.monotonic_ns()` (CLOCK_MONOTONIC). Chỉ dùng để **tính khoảng thời gian** trong cùng một tiến trình/host. Không trừ timestamp monotonic của host này cho host khác; trong VM hiện tại các namespace dùng chung kernel nên giá trị cùng gốc, nhưng đặc tả không dựa vào điều đó.

## 3. Schema cấu hình workload (`schema_version: 1`)

File JSON UTF-8, kiểm tra bằng `python3 workload/config.py <file>` (mã thoát 0 = hợp lệ, 2 = lỗi, in danh sách lỗi). Dùng JSON vì Python hệ thống của Ubuntu không có sẵn YAML; không cần cài thêm gói.

### 3.1. Bảng trường

| Trường | Kiểu | Đơn vị | Ràng buộc | Ý nghĩa |
|---|---|---|---|---|
| `schema_version` | int | — | `= 1` | Phiên bản schema |
| `config_id` | string | — | regex ở §2 | Định danh cấu hình workload |
| `description` | string | — | tùy chọn | Mô tả; ghi rõ “minh họa” nếu là ví dụ |
| `run_kind` | string | — | `smoke` \| `benchmark` | `smoke`: bài thử theo số request; `benchmark`: đo theo thời lượng |
| `protocol` | string | — | `= "tcp-binary-v1"` | Giao thức ứng dụng; HTTP chưa hỗ trợ |
| `network.clients` | list[object] | — | ≥1 phần tử `{name, ip}`; `name ∈ {c1,c2}`, duy nhất; `ip` phải khớp topology | Client logic |
| `network.servers` | list[object] | — | ≥1 phần tử `{name, ip, port}`; `name ∈ {a1,a2}`; `ip` khớp topology; `port = 8000` | Server emulator |
| `network.client_assignment` | string | — | `= "round_robin"` | Flow *i* → `clients[i mod nc]`, `servers[i mod ns]` |
| `workload.req_size_bytes` | int | byte | `[474, 16 777 216]` | **Tổng byte frame request** (§4.1) |
| `workload.resp_size_bytes` | int | byte | `[529, 16 777 216]` | **Tổng byte frame response** (§4.1) |
| `workload.rate_rps_per_flow` | float | request/s/flow | `(0, 1000]` | Tốc độ **mục tiêu** theo lịch gửi (§3.4) |
| `workload.concurrency` | int | flow | `1..8`; benchmark: `{1,2,4,8}` | Số kết nối TCP đồng thời tổng cộng từ các client |
| `workload.service_delay_ms` | float | ms | `[0, 10000]` | Thời gian chờ giả lập tại server cho mỗi request |
| `execution.warmup_sec` | float | s | `≥ 0`; benchmark `≥ 2` | Request có lịch gửi trong khoảng này được gắn `is_warmup=1` |
| `execution.duration_sec` | float | s | `> 0`; benchmark `≥ 10` | Thời lượng đo sau warm-up |
| `execution.max_requests_per_flow` | int \| null | request | smoke: bắt buộc `≥1`; benchmark: `null` | Giới hạn số request mỗi flow |
| `execution.timeout_ms` | int | ms | `[1, 60000]` | Response đến muộn hơn giá trị này → `TIMEOUT` |
| `execution.seed` | int | — | `≥ 0` | Ghi lại để tái lập. v1 dùng lịch gửi tất định, chưa có thành phần ngẫu nhiên |

Ràng buộc chéo: `warmup_sec + duration_sec + timeout_ms/1000 + 15 < 600` (giới hạn `networkctl exec`); với smoke, `(max_requests_per_flow − 1)/rate ≤ warmup_sec + duration_sec`. Kích thước tối thiểu 474/529 byte là chỗ cần cho header 8 byte + metadata JSON trong trường hợp dài nhất (ID 64 ký tự, số thứ tự 9 chữ số); `config.py` tính trực tiếp từ mã, không nhập tay.

### 3.2. Ví dụ cấu hình hợp lệ — **minh họa**

[`workload/configs/example-benchmark-4flow.json`](../workload/configs/example-benchmark-4flow.json) — chưa hiệu chỉnh qua pilot, không phải dữ liệu đo:

```json
{
  "schema_version": 1,
  "config_id": "example_benchmark_4flow_v1",
  "description": "VÍ DỤ MINH HỌA schema benchmark: chưa hiệu chỉnh qua pilot, chưa dùng để đo; không phải dữ liệu đo.",
  "run_kind": "benchmark",
  "protocol": "tcp-binary-v1",
  "network": {
    "clients": [{"name": "c1", "ip": "10.18.1.10"}, {"name": "c2", "ip": "10.18.2.10"}],
    "servers": [{"name": "a1", "ip": "10.18.3.11", "port": 8000},
                {"name": "a2", "ip": "10.18.3.12", "port": 8000}],
    "client_assignment": "round_robin"
  },
  "workload": {"req_size_bytes": 1024, "resp_size_bytes": 65536, "rate_rps_per_flow": 10.0,
               "concurrency": 4, "service_delay_ms": 5.0},
  "execution": {"warmup_sec": 5, "duration_sec": 30, "max_requests_per_flow": null,
                "timeout_ms": 5000, "seed": 42}
}
```

Cấu hình bài thử tuần 1 là [`smoke-c1-a1.json`](../workload/configs/smoke-c1-a1.json): 1 flow c1→a1, request 1024 B, response 4096 B, 5 request/s, service delay 5 ms, 10 request, timeout 2000 ms.

### 3.3. Phân luồng và offered load mục tiêu

Round-robin với `clients=[c1,c2]`, `servers=[a1,a2]`, concurrency 4 cho: flow0 c1→a1, flow1 c2→a2, flow2 c1→a1, flow3 c2→a2. Mỗi tiến trình client chỉ chạy các flow gán cho tên của nó (`--client-name`), runner nhiều client sẽ chạy hai tiến trình song song qua `networkctl exec`.

Offered load **mục tiêu ở tầng ứng dụng, tính riêng từng chiều** (link full-duplex, không cộng hai chiều):

- client→server: `offered_c2s_mbps = concurrency × rate_rps_per_flow × req_size_bytes × 8 / 10^6`
- server→client: `offered_s2c_mbps = concurrency × rate_rps_per_flow × resp_size_bytes × 8 / 10^6`

Giá trị này chưa gồm header TCP/IP/Ethernet nên tải trên dây cao hơn. Ví dụ minh họa ở §3.2: `4 × 10 × 65536 × 8 / 10^6 = 20,97 Mbps` chiều server→client. Việc chọn tải để profile A bão hòa link leaf–spine 25 Mbps mà B chưa bão hòa thuộc pilot các tuần sau (N18-018), phải đo xác nhận chứ không suy ra từ công thức.

### 3.4. Ngữ nghĩa rate: lịch gửi độc lập với phản hồi (open loop)

- Mỗi flow có lịch gửi cố định `t_k = t0 + k / rate_rps_per_flow`, `k = 0, 1, …`. Client gửi request *k* tại `t_k` **dù response trước đã về hay chưa**; nhiều request có thể nằm trên cùng kết nối (pipelining), server xử lý FIFO theo kết nối.
- Ghi `scheduled_send_mono_ns`, `send_mono_ns` thực tế và `send_lag_ms = send − scheduled` cho từng request.
- **Rate mục tiêu** = `rate_rps_per_flow` trong cấu hình. **Rate thực đạt** của flow = `(n − 1) / (t_send_cuối − t_send_đầu)` trên các request đo (is_warmup=0), n ≥ 2.
- Lượt **duy trì được tải mục tiêu** (`load_sustained = true`) khi mọi flow có rate thực đạt ≥ **95 %** rate mục tiêu **và** p95 `send_lag_ms` ≤ **0,5 × khoảng giữa hai request**. Không đủ mẫu → `null`.
- Lượt có `load_sustained ≠ true` **phải được đánh dấu** trong kết quả và **không được dùng làm cặp đối chứng cùng offered load** khi so sánh A/B (TV3 xử lý ở N18-035).
- Runner 1/2/4/8 flow và kiểm tra tải ở mức cao thuộc N18-010/018/022; tuần 1 chỉ chốt định nghĩa và hiện thực cho một flow.

## 4. Giao thức `tcp-binary-v1` (TCP/8000)

Chồng giao thức: **ứng dụng tùy biến → TCP (cổng 8000) → IPv4 → Ethernet**.

### 4.1. Framing và định nghĩa size

```text
+----------------+----------------+-------------------------+----------------------+
| meta_len       | pad_len        | metadata JSON (UTF-8)   | padding (byte 'X')   |
| uint32, big-end| uint32, big-end| meta_len byte           | pad_len byte         |
+----------------+----------------+-------------------------+----------------------+
|<------------------- frame_bytes = 8 + meta_len + pad_len ---------------------->|
```

- **`req_size_bytes`/`resp_size_bytes` là tổng byte frame ứng dụng**, gồm header 8 byte + JSON + padding; không gồm header TCP/IP/Ethernet.
- Metadata luôn có trường `frame_bytes`; bên nhận kiểm tra `frame_bytes` bằng số byte thực nhận trên dây và bằng size cấu hình.
- Nếu `8 + len(JSON)` lớn hơn size yêu cầu, bộ mã hóa **báo lỗi** (`FrameError`), không cắt metadata hay gửi frame sai kích thước. Validator chặn từ trước bằng ngưỡng ở §3.1.
- Giới hạn an toàn: metadata ≤ 64 KiB, frame ≤ 16 MiB.

### 4.2. Metadata request (client → server)

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `msg`, `protocol` | string | `"request"`, `"tcp-binary-v1"` |
| `run_id`, `config_id` | string | Theo §2 |
| `req_id` | string | `{run_id}_f{flow_id}_r{seq}` |
| `flow_id`, `seq` | int | Chỉ số flow (0..concurrency−1), số thứ tự trong flow (0, 1, …) |
| `client_host` | string | `c1`/`c2` |
| `client_send_utc` | string | UTC lúc tạo request (đối chiếu log) |
| `resp_size_bytes` | int | Size frame response yêu cầu |
| `service_delay_ms` | float | Service delay yêu cầu server thực hiện |
| `frame_bytes` | int | Tổng byte frame này |

### 4.3. Metadata response (server → client)

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `msg`, `protocol` | string | `"response"`, `"tcp-binary-v1"` |
| `run_id`, `req_id`, `flow_id`, `seq` | | Sao chép từ request để khớp |
| `server_host` | string | `a1`/`a2` |
| `status` | string | `OK` hoặc `ERR_INVALID_REQ` |
| `server_recv_mono_ns` | int | Lúc server **đọc xong** request khỏi socket |
| `server_service_start_mono_ns` | int | Lúc worker bắt đầu xử lý request (sau các request trước trên cùng kết nối) |
| `server_send_mono_ns` | int | Ngay trước khi mã hóa và gửi response |
| `server_queue_ms` | float | `(service_start − recv)/10^6`: chờ trong hàng FIFO của server |
| `server_service_ms` | float | `(send − service_start)/10^6`: service delay **thực tế** (gồm sai số `sleep`) |
| `server_proc_ms` | float | `(send − recv)/10^6 = server_queue_ms + server_service_ms` |
| `frame_bytes` | int | Tổng byte frame này |

Server không chạy mô hình; nó dùng `resp_size_bytes`/`service_delay_ms` trong request, kiểm tra miền giá trị và `run_id` mong đợi (nếu được cấp), trả `ERR_INVALID_REQ` nếu sai.

## 5. Chỉ số thời gian phía ứng dụng

| Chỉ số | Công thức | Ghi chú |
|---|---|---|
| `app_response_ms` | `(recv_mono_ns − send_mono_ns) / 10^6` trên client | Từ ngay trước `sendall` request tới khi đọc đủ frame response. **Thay tên cho `app_rtt_ms` của bản nháp**; đây không phải RTT mạng |
| `server_proc_ms` | Từ response (§4.3) | Thời gian request nằm trong ứng dụng server |
| `network_residual_est_ms` | `app_response_ms − server_proc_ms` | **Ước lượng phần dư**, gồm truyền/hàng đợi mạng hai chiều, thời gian truyền frame `L/R`, bộ đệm socket/kernel, lập lịch tiến trình. **Không gọi là “RTT mạng thuần túy”** |
| `residual_valid` | `1` nếu `network_residual_est_ms ≥ 0`, ngược lại `0` | Mẫu âm **giữ nguyên giá trị** và bị đánh dấu bất hợp lệ; **không ép về 0**, không dùng trong thống kê residual |

`server_proc_ms` và `app_response_ms` đo bằng hai đồng hồ monotonic ở hai tiến trình nhưng mỗi giá trị là một hiệu trên cùng một đồng hồ, nên phép trừ hợp lệ. Định nghĩa thống kê (nearest-rank, cửa sổ, warm-up) theo [metrics-spec.md](metrics-spec.md).

## 6. Log đầu ra và mã thoát

Mỗi lượt ghi vào `evidence/<khu-vực>/<run_id>/…`. Giá trị không có ghi **ô trống**, không ghi 0.

### 6.1. `client-requests.csv` — một dòng mỗi request

| Cột | Đơn vị | Ý nghĩa |
|---|---|---|
| `run_id`, `config_id`, `profile`, `run_kind` | — | §2 |
| `is_warmup` | 0/1 | 1 nếu lịch gửi nằm trong `warmup_sec` |
| `flow_id`, `client_host`, `server_host`, `server_ip`, `server_port`, `src_port` | — | Định danh kết nối (5-tuple) |
| `req_id`, `seq` | — | §4.2 |
| `scheduled_send_mono_ns`, `send_mono_ns`, `recv_mono_ns` | ns | Đồng hồ monotonic client |
| `send_utc`, `recv_utc` | ISO-8601 | Đối chiếu log |
| `send_lag_ms` | ms | `send − scheduled` |
| `req_bytes_sent`, `resp_bytes_expected`, `resp_bytes_received` | byte | Size frame ứng dụng |
| `app_response_ms`, `server_queue_ms`, `server_service_ms`, `server_proc_ms`, `network_residual_est_ms`, `residual_valid` | ms, 0/1 | §5 |
| `status` | — | `OK`, `TIMEOUT`, `CONN_ERROR`, `SIZE_MISMATCH`, `INVALID_RESPONSE`, `PROTOCOL_ERROR`, `SEND_ERROR`, `NOT_SENT` |
| `error` | — | Mô tả lỗi |

Response có `req_id` không khớp request đang chờ được ghi vào `unmatched_responses` của `client-summary.json`; request bị thiếu response tương ứng sẽ thành `TIMEOUT`.

### 6.2. Các file khác

- `client-summary.json`: số request mong đợi, đếm theo status, `unmatched_responses`, offered load mục tiêu, `load_check` (rate thực đạt, p95 send lag, `load_sustained`), thống kê nearest-rank của `app_response_ms`/`server_proc_ms`/`network_residual_est_ms` (chỉ mẫu OK, is_warmup=0), `exit_code`.
- `server-events.jsonl`: sự kiện `listening`, `connection_open/close`, `request` (byte nhận/gửi, mọi mốc monotonic, `server_*_ms`, `status`, `fault_injected`), `protocol_error`.
- `server-summary.json`: số request đã phục vụ/hợp lệ/không hợp lệ, lỗi framing, timeout, `exit_code`.

### 6.3. Mã thoát

| Chương trình | 0 | Khác 0 |
|---|---|---|
| `client.py` | Mọi response mong đợi hợp lệ (ID, size, status) | 2 cấu hình/tham số; 3 lỗi kết nối; 4 sai ID/size/status/framing; 5 timeout |
| `server.py` | Phục vụ đủ `--expect-requests` request hợp lệ, không lỗi framing | 1 |
| `smoke_test.py` | Lượt chính 10/10 hợp lệ, client/server mã 0; với `--negative`, mọi ca lỗi trả đúng mã mong đợi | 1 |

`server.py --fault wrong-id|short-response` **chỉ dùng cho kiểm thử âm tính**, được ghi `fault_injected` trong log và không bao giờ là cấu hình đo.

## 7. Hướng dẫn chạy

Trong Ubuntu VM, tại thư mục clone repo (không kích hoạt venv):

```bash
python3 -m unittest discover -s tests -v
python3 workload/config.py workload/configs/smoke-c1-a1.json
sudo /usr/bin/python3 control/networkctl.py start --profile A
sudo /usr/bin/python3 workload/smoke_test.py --label tv2-smoke --negative
sudo /usr/bin/python3 control/networkctl.py stop
```

`smoke_test.py` đọc `networkctl status` để lấy profile, khởi động `server.py` trong a1 và `client.py` trong c1 qua `networkctl exec`, chờ server lắng nghe (`ss -ltn`), rồi lưu `environment.json`, `source-manifest.json`, `network-status.json`, log từng ca và `result.json`. Chạy thủ công từng chương trình:

```bash
sudo /usr/bin/python3 control/networkctl.py exec --timeout 60 a1 -- /usr/bin/python3 workload/server.py \
  --host-name a1 --run-id manual-1 --out evidence/tv2-week1/manual-1/server --expect-requests 10
# terminal khác
sudo /usr/bin/python3 control/networkctl.py exec --timeout 60 c1 -- /usr/bin/python3 workload/client.py \
  --config workload/configs/smoke-c1-a1.json --client-name c1 --run-id manual-1 --profile A \
  --out evidence/tv2-week1/manual-1/client
```

Trên macOS/Windows chỉ chạy được unit test và chế độ loopback trong test (`NHOM18_ALLOW_LOOPBACK=1`, chỉ chấp nhận `127.0.0.1`); không dùng loopback làm minh chứng mạng.

## 8. Bài thử khởi động tuần 1

**Môi trường thực tế:** VM `Nhom18-W1` (UTM, Ubuntu 24.04 ARM64, Python 3.12.3) trên máy Mac của TV1; testbed 10 node profile A. Lượt chạy do phiên hỗ trợ AI thực hiện theo yêu cầu của người dùng, **không phải** TV2 chạy trên máy của TV2. TV2 nên tự chạy lại trên máy của mình để kiểm tra tính tái lập.

| Lượt (run_id) | Commit mã | Kết quả |
|---|---|---|
| [`20261118T112728069663Z-tv2-smoke`](../evidence/tv2-week1/20261118T112728069663Z-tv2-smoke/result.json) | `6d7df69` | **10/10 OK**; client 0, server 0; 3/3 ca âm tính đúng mã |
| [`20261118T113018044375Z-tv2-smoke-rerun`](../evidence/tv2-week1/20261118T113018044375Z-tv2-smoke-rerun/result.json) | `af83849` | **10/10 OK**; client 0, server 0; 3/3 ca âm tính đúng mã |

Giá trị đo (lượt đầu, nearest-rank, n = 10, cấu hình `smoke_c1_a1_v1`, profile A; chỉ mô tả bài thử này, không phải benchmark):

| Chỉ số | min | p50 | max |
|---|---:|---:|---:|
| `app_response_ms` | 10,575 | 11,097 | 12,174 |
| `server_proc_ms` (yêu cầu 5 ms) | 5,387 | 6,092 | 6,728 |
| `network_residual_est_ms` (10/10 hợp lệ) | 4,278 | 5,334 | 5,553 |

Rate thực đạt 4,999 request/s so với mục tiêu 5,0; p95 `send_lag_ms` 4,908 ms ≤ 100 ms → `load_sustained = true`.

**Ca âm tính (lỗi tạo có chủ đích, không tính là kiểm thử kết nối đạt):** server đổi `req_id` của request seq 3 → client mã 4, response lạ được ghi `unmatched_responses`; server trả response thiếu 100 byte ở seq 3 → `SIZE_MISMATCH`, mã 4; không có server ở a1:8000 → `CONN_ERROR`, mã 3.

**Quan sát:** qua hai lượt, `server_service_ms` dài hơn 5 ms yêu cầu khoảng 0,12–1,39 ms do độ phân giải `sleep` trong VM; `server_queue_ms` 0,09–0,68 ms là thời gian chuyển request từ luồng đọc sang luồng xử lý. Vì vậy phân tích dùng `server_proc_ms` **đo được**, không dùng giá trị cấu hình. `send_lag_ms` tới ~5 ms, nhỏ so với khoảng 200 ms ở 5 request/s nhưng cần theo dõi khi tăng rate.

## 9. Giới hạn và việc tuần sau

- Chưa có runner 1/2/4/8 flow, chưa chạy từ c2/a2, chưa hiệu chỉnh offered load gây bão hòa (N18-010/014/018/022).
- `seed` chưa dùng; lịch gửi tất định.
- Server phục vụ FIFO theo kết nối; request pipelined chờ trong server được tính vào `server_queue_ms`, chờ trong bộ đệm socket trước khi được đọc thì nằm trong `network_residual_est_ms`.
- HTTP chưa đặc tả.

## 10. Thay đổi so với bản nháp v0

| Bản nháp v0 (PDF) | v1.0 | Lý do |
|---|---|---|
| Bảng schema `clients: list[string]`, `servers: ["ip:port"]` nhưng ví dụ dùng object | Cả bảng và ví dụ dùng `clients: [{name, ip}]`, `servers: [{name, ip, port}]`; validator từ chối dạng chuỗi | Schema và ví dụ phải giống nhau |
| `protocol: "tcp" \| "http"` | Chỉ `tcp-binary-v1`, cổng 8000; HTTP là mở rộng | HTTP chưa được đặc tả đầy đủ |
| `req/resp_size_bytes ≥ 128` | Size = tổng frame; tối thiểu 474/529 byte tính từ metadata; thiếu chỗ báo lỗi | 128 byte không chứa nổi metadata |
| Không nói rate mở hay đóng | Open loop, rate mục tiêu vs thực đạt, `load_sustained` | Tránh so sánh A/B khác offered load |
| `app_rtt_ms`, `net_rtt_est_ms = max(0, …)` “độ trễ mạng thuần túy” | `app_response_ms`, `network_residual_est_ms` ước lượng; mẫu âm `residual_valid=0` | Không ép âm về 0; không gọi là RTT mạng thuần |
| Offered load cộng request + response | Tính riêng từng chiều | Link full-duplex |
| `server_proc_ms` chỉ một giá trị | Tách `server_queue_ms` + `server_service_ms` | Phân biệt chờ hàng đợi và xử lý |
| `send_ts_ns` không nói đồng hồ | `*_utc` để đối chiếu, `*_mono_ns` để tính khoảng | Quy ước chung với TV3 |

## 11. Review

TV3 review theo phiếu trong [qa/week1-review.md](../qa/week1-review.md#phiếu-review-n18-002--tv3-review-tv2): schema, cách ghi thời gian, khả năng tính metric từ log. Kết quả kiểm tra log tự động của TV4 ở [evidence/tv4-week1](../evidence/tv4-week1/README.md).
