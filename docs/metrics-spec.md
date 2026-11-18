# Đặc tả metric, baseline và cách đo (N18-003)

| Mục | Nội dung |
|---|---|
| Task | **N18-003**, tuần 1 — Đặc tả metrics, baseline và protocol đo |
| Người phụ trách (DRI) | TV3 |
| Người review | TV1 (công thức, nguồn dữ liệu, chạy lại bài thử) |
| Phiên bản | **v1.0**, 18/11/2026. Thay bản nháp v0 `Báo cáo Đặc tả Metrics … W1.pdf` (ngoài repo); thay đổi ở [§11](#11-thay-đổi-so-với-bản-nháp-v0) |
| Trạng thái | **Hoàn thành** — TV1 đã review (theo xác nhận của nhóm trưởng TV1 ngày 18/11/2026) |
| Mã nguồn | [`measurement/week1_probe.py`](../measurement/week1_probe.py), [`measurement/to_csv.py`](../measurement/to_csv.py), [`tools/stats.py`](../tools/stats.py) |
| Minh chứng | [`evidence/tv3-week1/`](../evidence/tv3-week1/README.md) |
| Liên quan | [Đặc tả workload](workload-spec.md) (định danh, log ứng dụng), [Bàn giao mạng TV1](network-handoff.md) (capacity link) |

## 1. Nguyên tắc chung

1. **Mỗi metric một ý nghĩa.** Không gộp RTT ICMP, thời gian phản hồi ứng dụng, thời gian xử lý server và phần dư ước lượng thành một chỉ số “RTT”.
2. **Raw giữ nguyên.** Output của `ping`, `iperf3`, counter và log ứng dụng được lưu nguyên văn; CSV sinh bằng chương trình, ghi `raw_file` + `raw_sha256`. Không nhập tay, không sửa raw.
3. **Không điền 0 cho dữ liệu không có.** Giá trị chưa đo/không áp dụng/không hợp lệ là **ô trống** kèm trạng thái (§5.3). 0 chỉ xuất hiện khi đo được đúng bằng 0 (ví dụ 0 gói mất).
4. **Định danh thống nhất với TV2** ([workload-spec §2](workload-spec.md#2-định-danh-và-thời-gian-thống-nhất-với-tv3)): mọi dòng CSV có `run_id`, `config_id` (trống với phép đo chẩn đoán không có workload) và `profile` (A/B, tách khỏi `config_id`).
5. **Thời gian:** `*_utc` (ISO-8601, `Z`) để đối chiếu nguồn; khoảng thời gian tính bằng đồng hồ monotonic hoặc trường thời lượng của công cụ, không trừ hai chuỗi UTC đọc từ hai nguồn khác nhau.
6. Kết quả đo trên VM chỉ mô tả testbed đã cấu hình; không suy ra hiệu năng Data Center thật.

## 2. Bảng metric

| Tên | Ý nghĩa | Công thức | Đơn vị | Nguồn / công cụ | Loại mẫu, cửa sổ |
|---|---|---|---|---|---|
| `icmp_rtt_ms` | RTT ICMP echo giữa hai host | giá trị `time=` mỗi reply | ms | `ping -D -n` trong namespace nguồn | 1 mẫu = 1 echo reply |
| `icmp_loss_pct` | Tỷ lệ mất gói ICMP đầu cuối | `(packets_tx − packets_rx) / packets_tx × 100` | % | dòng tổng kết `ping` | cả lượt ping |
| `app_response_ms` | Thời gian phản hồi tầng ứng dụng | `(recv_mono_ns − send_mono_ns)/10^6` | ms | `client-requests.csv` (TV2) | 1 mẫu = 1 request OK, `is_warmup=0` |
| `server_proc_ms` | Thời gian request nằm trong ứng dụng server | `server_queue_ms + server_service_ms` | ms | metadata response / `server-events.jsonl` | như trên |
| `network_residual_est_ms` | **Ước lượng** phần không thuộc server: mạng hai chiều + truyền frame + bộ đệm + lập lịch | `app_response_ms − server_proc_ms`; chỉ dùng mẫu `residual_valid=1` | ms | tính từ hai cột trên | như trên; mẫu âm là bất hợp lệ, không ép 0 |
| `d_trans_ms` (lý thuyết) | Độ trễ truyền một lượng dữ liệu L qua link R | `L × 8 / R` (L byte, R bit/s) × 1000 | ms | tính toán, không đo | ghi rõ L gồm/không gồm header |
| `app_goodput_mbps` | Goodput ứng dụng của workload | `Σ resp_bytes_received × 8 / T / 10^6` theo chiều server→client (tương tự chiều ngược với `req_bytes_sent`) | Mbps | `client-requests.csv` | cửa sổ đo `T` sau warm-up; byte = frame ứng dụng |
| `iperf3_goodput_mbps` | Goodput TCP payload của iperf3 | `end.sum_received.bits_per_second / 10^6` (phía nhận); phía gửi lấy `sum_sent` | Mbps | `iperf3 -J` | cửa sổ đo sau `-O`; **chỉ dùng chẩn đoán** |
| `tx_mbps`, `rx_mbps` | Throughput tại interface, từng chiều | `Δbytes × 8 / Δt / 10^6` | Mbps | counter kernel `ip -s -j link` (`/sys/class/net/<if>/statistics`) | mỗi cửa sổ lấy mẫu; Δt đo thực tế |
| `tx_util_pct`, `rx_util_pct` | Mức sử dụng link từng chiều | `tx_mbps / capacity_mbps × 100` (tương tự rx) | % | counter + capacity từ cấu hình `tc` của TV1 | mỗi cửa sổ |
| `utilization_pct` | Chỉ số tổng hợp của link | `max(tx_util_pct, rx_util_pct)` | % | tính từ hai cột trên | mỗi cửa sổ |
| `tx_dropped_pkts`, `rx_dropped_pkts` | Gói bị hủy tại interface trong cửa sổ | `Δ dropped` | **gói** | counter kernel | mỗi cửa sổ |
| `tcp_retransmits` | Số segment TCP truyền lại | delta bộ đếm | segment | `iperf3` (`retransmits`), sau này `ss -ti` | theo lượt/cửa sổ |

**Phân biệt bắt buộc:**

- *Throughput tại interface* đếm byte khung Ethernet đi qua interface (gồm header L2–L4, ACK, ARP, ICMP…). *Goodput ứng dụng* chỉ đếm byte frame ứng dụng (workload) hoặc payload TCP (iperf3). Hai số không bằng nhau và không được thay thế cho nhau.
- `tx_dropped`/`rx_dropped` và `tcp_retransmits` **không phải tỷ lệ mất gói đầu cuối**. Drop counter cho biết hàng đợi/interface nào hủy gói; retransmission cho biết TCP phải gửi lại (có thể do mất gói, do reorder hay timeout). Tỷ lệ mất gói đầu cuối trong dự án chỉ lấy từ ICMP (gửi/nhận).
- Capacity link lấy theo **rate HTB thực cấu hình** (`tc class show`), không theo `speed 10000` mà OVS báo cho veth. Hiện tại leaf–spine 25 Mbps, các link khác 100 Mbps ([network-handoff §2](network-handoff.md#2-topology-và-địa-chỉ)); cần đọc lại từ `tc.json` của mỗi lượt nếu TV1 đổi cấu hình.
- Ví dụ `d_trans` **minh họa**: một frame ứng dụng 4096 B qua link 25 Mbps → `4096 × 8 / 25·10^6 = 1,31 ms` (chưa gồm header TCP/IP/Ethernet). Đây là phép tính lý thuyết, không phải giá trị đo.

## 3. Cửa sổ lấy mẫu

- **Counter interface (tuần 3+):** chu kỳ danh định `sampling_interval_s = 1,0`. Mỗi mẫu ghi `window_start_utc`, `window_end_utc` và `window_s` **đo bằng đồng hồ monotonic giữa hai lần đọc**, không dùng giá trị danh định. Dùng counter kernel đọc trực tiếp (OVSDB `Interface.statistics` có thể trễ cập nhật — kinh nghiệm của TV1 trong evidence mạng).
- **Workload:** cửa sổ đo của một lượt = từ `t0 + warmup_sec` tới `t0 + warmup_sec + duration_sec`; chỉ request có lịch gửi trong cửa sổ (`is_warmup=0`) được thống kê.
- **iperf3:** cửa sổ đo là khoảng sau `-O`; thời lượng lấy từ `end.sum_sent.seconds`/`end.sum_received.seconds`, **không cộng trường `seconds` của từng interval** (xem phát hiện F2, §9.3).
- **Ping:** mỗi reply là một mẫu; lượt ping là cửa sổ tính `icmp_loss_pct`.

## 4. Warm-up, counter reset và giá trị chưa đo

### 4.1. Loại warm-up

- Workload: loại mọi request `is_warmup=1` khỏi thống kê và goodput; vẫn giữ trong raw CSV.
- iperf3: dùng `-O <giây>`; interval có `omitted=true` bị loại; tổng kết `end.sum_*` của iperf3 đã không gồm phần omit.
- Counter: bỏ mọi cửa sổ có `window_start_utc` trước thời điểm kết thúc warm-up của lượt workload tương ứng.

### 4.2. Counter reset

Counter kernel là 64 bit nên không xử lý wrap-around. Một cửa sổ là **không hợp lệ** (`value_status=counter_reset`, giá trị trống) khi: delta âm; `ifindex` của interface đổi giữa hai lần đọc; hoặc `session_id` của testbed đổi (topology được dựng lại). Không nối delta qua lần reset, không thay bằng 0.

### 4.3. Trạng thái giá trị

| `value_status` | Nghĩa | Giá trị |
|---|---|---|
| `ok` | Đo/tính hợp lệ | số |
| `missing` | Không có dữ liệu (công cụ lỗi, không có reply) | trống |
| `invalid` | Có dữ liệu nhưng vi phạm điều kiện (ví dụ residual âm) | trống trong bảng tổng hợp, giữ giá trị gốc ở raw |
| `counter_reset` | §4.2 | trống |
| `not_applicable` | Metric không áp dụng cho lượt (ví dụ `config_id` của phép đo chẩn đoán) | trống |

## 5. Thống kê

### 5.1. Percentile nearest-rank

Với n mẫu sắp xếp tăng dần `x(1) ≤ … ≤ x(n)`: `rank = ⌈p/100 × n⌉`, `P_p = x(rank)`. Không nội suy. Hiện thực tại [`tools/stats.py`](../tools/stats.py).

Mỗi giá trị p50/p95/p99 phải ghi kèm **loại mẫu** (ICMP reply, request ứng dụng OK sau warm-up, …) và **số mẫu n**. Với n = 20: p95 = mẫu thứ 19, p99 = mẫu thứ 20 (= max). p99 chỉ khác max khi n > 100; báo cáo không diễn giải p99 như “đuôi” khi n nhỏ. Tập rỗng → giá trị trống, không phải 0.

### 5.2. Trung bình và độ dao động

Trung bình số học trên mẫu hợp lệ; độ dao động giữa các lần lặp (N18-039) dùng độ lệch chuẩn mẫu và min/max, ghi số lần lặp.

### 5.3. Sai số làm tròn của ping

`ping` (iputils 20240117) in từng reply với 3 chữ số có nghĩa (ví dụ `time=4.99 ms`) nhưng dòng tổng kết `min/avg/max/mdev` tính từ giá trị chưa làm tròn (`4.321/4.560/5.234`). Vì vậy min/mean/max tính từ CSV có thể lệch tối đa nửa đơn vị chữ số in ra (0,005 ms với RTT 1–10 ms). CSV ghi **cả** giá trị tính từ mẫu (`icmp_rtt_*`) và giá trị ping báo (`ping_reported_*`); đối chiếu chấp nhận sai số này (phát hiện F1, §9.3).

## 6. Định dạng CSV

### 6.1. Đã hiện thực (bài thử tuần 1)

`ping-samples.csv` — một dòng mỗi reply: `run_id, config_id, profile, src_host, dst_host, sample_type, icmp_seq, ts_utc, icmp_rtt_ms, ttl, reply_bytes, raw_file, raw_line`.

`ping-summary.csv` — một dòng mỗi lượt: `packets_tx, packets_rx, icmp_loss_pct, ping_reported_loss_pct, rtt_sample_count, icmp_rtt_{min,mean,p50,p95,p99,max}_ms, ping_reported_{min,avg,max,mdev}_ms, percentile_method, first_sample_utc, last_sample_utc, raw_file, raw_sha256` (cùng các cột định danh).

`iperf3-intervals.csv` — một dòng mỗi interval: `interval_index, start_s, end_s, seconds, seconds_end_minus_start, timing_suspect, omitted, bytes, goodput_mbps, retransmits, raw_file`. `start_s/end_s` tương đối theo mốc thời gian của iperf3 (mốc được đặt lại khi hết `-O`).

`iperf3-summary.csv` — `protocol, parallel_streams, omit_s, duration_s_requested, test_start_utc, measured_intervals, timing_suspect_intervals, measured_bytes_from_intervals, interval_bytes_match_sender, sender_{seconds,bytes,goodput_mbps}, tcp_retransmits, receiver_{seconds,bytes,goodput_mbps}, interval_goodput_{min,max}_mbps` (bỏ interval `timing_suspect`), `raw_file, raw_sha256`.

### 6.2. Kế hoạch cho tuần 3–6 (chưa hiện thực)

`link_metrics.csv` (N18-011/019): `run_id, config_id, profile, window_start_utc, window_end_utc, window_s, link_name, interface, capacity_mbps, tx_bytes_delta, rx_bytes_delta, tx_mbps, rx_mbps, tx_util_pct, rx_util_pct, utilization_pct, tx_dropped_pkts, rx_dropped_pkts, value_status`.

`app_metrics.csv` (N18-015, tổng hợp từ log TV2 theo cửa sổ hoặc theo lượt): `run_id, config_id, profile, flow_id, window_*, requests_ok, requests_failed, load_sustained, app_response_{p50,p95,p99}_ms, server_proc_p50_ms, network_residual_est_p50_ms, residual_invalid_count, app_goodput_s2c_mbps, app_goodput_c2s_mbps, sample_count`.

## 7. Baseline và protocol đo

1. **Baseline idle:** trước mỗi loạt đo, chạy ping (≥ 20 gói, 0,2 s) giữa từng cặp client–server khi **không có** workload/iperf3 nào; lưu raw. Đây là RTT nền của testbed.
2. **Chẩn đoán capacity:** iperf3 chạy **riêng**, sau baseline; chỉ để kiểm tra đường truyền/capacity. Không gọi là benchmark AI inference, và ping chạy đồng thời với iperf3 là “RTT khi có tải nền”, không phải mạng rảnh.
3. **Lượt workload (tuần 4+):** cùng lúc thu log TV2, counter theo cửa sổ 1 s và (tùy chọn) ping nền tần số thấp có nhãn `loaded`.
4. Mọi lượt ghi `environment.json` (kernel, gói, boot ID, commit), `network-status.json` (profile, session, config hash) và `source-manifest.json`.
5. So sánh A/B chỉ dùng cặp lượt cùng `config_id`, `load_sustained = true` ở cả hai, cùng capacity link (N18-035).

## 8. Bài thử khởi động tuần 1 và hướng dẫn chạy

```bash
sudo /usr/bin/python3 control/networkctl.py start --profile A
sudo /usr/bin/python3 measurement/week1_probe.py --label tv3-probe
sudo /usr/bin/python3 control/networkctl.py stop
# chuyển lại một raw sẵn có sang CSV ở thư mục khác (không ghi đè evidence):
python3 measurement/to_csv.py ping evidence/tv3-week1/<run>/ping-c1-a1.txt --run-id <run> --profile A \
  --src c1 --dst a1 --out-dir /tmp/recheck
```

`week1_probe.py` từ chối chạy nếu testbed không ở profile A hoặc đang có lệnh workload khác. Trình tự: (1) `ping -D -n -c 20 -i 0.2 -W 2 10.18.3.11` từ c1 khi chưa có tải; (2) `iperf3 -s -1 -p 5201 -J` trên a1; (3) `iperf3 -c 10.18.3.11 -p 5201 -P 1 -t 10 -O 2 -J` từ c1 — tổng 12 s, đo 10 s sau 2 s bỏ qua; (4) chuyển raw sang CSV.

## 9. Kết quả bài thử tuần 1

**Môi trường thực tế:** VM `Nhom18-W1` (UTM, Ubuntu 24.04 ARM64, kernel 6.8.0-149-generic, iperf3 3.16-1build2, iputils-ping 20240117) trên máy Mac của TV1, testbed profile A. Lượt chạy do phiên hỗ trợ AI thực hiện theo yêu cầu của người dùng, **không phải** TV3 chạy trên máy của TV3. Đây là bài đo chẩn đoán.

| Lượt (run_id) | Commit | Ghi chú |
|---|---|---|
| [`20261118T112753790043Z-tv3-probe`](../evidence/tv3-week1/20261118T112753790043Z-tv3-probe/result.json) | `6d7df69` | Công cụ đạt; **CSV iperf3 có lỗi F2** (giữ nguyên làm lịch sử) |
| [`20261118T112952839193Z-tv3-probe-rerun`](../evidence/tv3-week1/20261118T112952839193Z-tv3-probe-rerun/result.json) | `af83849` | Sau khi sửa F2; dùng làm kết quả tuần 1 |

### 9.1. Giá trị (lượt rerun)

| Chỉ số | Giá trị | Nguồn |
|---|---|---|
| ICMP gửi/nhận, `icmp_loss_pct` | 20/20, 0 % | `ping-summary.csv` |
| `icmp_rtt_ms` (ICMP reply, n = 20, nearest-rank) | min 4,32; p50 4,49; p95 4,99; p99 = max 5,23 | `ping-summary.csv` |
| ping tự báo min/avg/max/mdev | 4,321 / 4,560 / 5,234 / 0,208 ms | raw |
| iperf3 goodput phía nhận / phía gửi | **23,872** / 23,909 Mbps | `iperf3-summary.csv` |
| Thời lượng đo (sender) | 9,999 s; 1 interval omit bị loại | raw `end.sum_sent` |
| TCP retransmits (phía gửi) | 12 | raw |
| Goodput theo interval (bỏ interval nghi vấn) | 19,84 – 28,46 Mbps | `iperf3-intervals.csv` |

Goodput ~23,9 Mbps với một luồng TCP qua đường c1→spine1→a1 có link leaf–spine 25 Mbps là phù hợp với capacity cấu hình, nhưng chỉ là kiểm tra hạ tầng.

### 9.2. Đối chiếu CSV với raw

- **RTT:** raw dòng 2 `[1795001392.918517] 64 bytes from 10.18.3.11: icmp_seq=1 ttl=62 time=4.99 ms` ↔ `ping-samples.csv` dòng `icmp_seq=1, ts_utc=2026-11-18T11:29:52.918517Z, icmp_rtt_ms=4.99, raw_line=2`. Toàn bộ 20 mẫu được TV4 so khớp tự động.
- **Throughput:** raw `end.sum_received.bits_per_second = 23871814.06135549` ↔ `iperf3-summary.csv` `receiver_goodput_mbps = 23.871814`. Tổng byte 10 interval đo = `sum_sent.bytes = 29 884 416` (`interval_bytes_match_sender = 1`).
- SHA-256 của raw trong CSV khớp file hiện tại → raw không bị sửa sau khi chuyển đổi.

Chi tiết từng phép so khớp: [qa-report.md của lần kiểm tra lại](../evidence/tv4-week1/20261118T113009015094Z-tv4-logcheck-recheck/qa-report.md).

### 9.3. Phát hiện từ kiểm tra log và cách sửa

| ID | Phát hiện thực tế | Sửa | Kiểm tra lại |
|---|---|---|---|
| F1 | Min/mean CSV (4,26 / 4,493) khác tổng kết ping (4,256 / 4,491) ở lượt đầu; kiểm tra so bằng tuyệt đối nên KHÔNG ĐẠT | Không phải lỗi converter: ping in mẫu đã làm tròn. Ghi sai số ±0,005 ms vào §5.3; checker dùng dung sai này (commit `af83849`) | Lượt rerun ĐẠT |
| F2 | iperf3 3.16 báo interval đầu sau `-O` có `seconds = 2,0007` trong khi `end − start` chỉ khoảng ±0,001 s (lặp lại ở cả hai lượt). Converter cũ cộng `seconds` → “khoảng đo” 11,0 s và lấy interval này làm goodput min 13,6 Mbps | Thời lượng lấy từ `end.sum_*`; thêm `seconds_end_minus_start`, `timing_suspect`; loại interval nghi vấn khỏi min/max; đối chiếu tổng byte interval với `sum_sent.bytes` (commit `af83849`) | Lượt rerun ĐẠT; goodput min 19,84 Mbps |

## 10. Giới hạn

- Mới đo một cặp c1→a1 trên profile A; chưa có counter interface, utilization, profile B hay workload ứng dụng trong cùng cửa sổ.
- Một luồng TCP iperf3 không đại diện workload request/response.
- `app_goodput_mbps`, `link_metrics.csv`, `app_metrics.csv` mới là đặc tả, hiện thực ở N18-011/015/019.

## 11. Thay đổi so với bản nháp v0

| Bản nháp v0 (PDF) | v1.0 | Lý do |
|---|---|---|
| “RTT tầng ứng dụng”, `rtt_p95/p99` chung với RTT ping | Tách `icmp_rtt_ms`, `app_response_ms`, `server_proc_ms`, `network_residual_est_ms` | Không gộp thành một RTT |
| Throughput từ iperf3 **hoặc** counter OVS như cùng một đại lượng | Tách throughput interface (counter) và goodput (ứng dụng / iperf3) | Khác đối tượng đếm |
| `utilization_pct` một giá trị, `tx_mbps/rx_mbps` | `tx_util_pct`, `rx_util_pct`; tổng hợp `max(tx, rx)` | Link full-duplex |
| `packet_loss_pct` lấy từ ping/iperf3 **hoặc** `tx_dropped/rx_dropped` | Loss chỉ từ ICMP gửi/nhận; drop là số gói delta theo cửa sổ; retransmit tách riêng | Drop/retransmit không phải loss đầu cuối |
| `config_id` = “Mã cấu hình (A/B)” | `config_id` (workload) và `profile` (mạng) là hai trường | Đồng bộ TV2 |
| Không nói warm-up, counter reset, thiếu dữ liệu | §4 | Tránh số 0 giả |
| p95/p99 không nêu cách tính | Nearest-rank, ghi loại mẫu + n | Tái lập được |
| Baseline “mạng rảnh” bằng `baseline.py` | Protocol §7: baseline idle tách khỏi iperf3; iperf3 là chẩn đoán | Không gọi mạng rảnh khi có tải |
| Capacity “do TV1 cung cấp” | Rate HTB từ `tc`, không dùng speed 10 Gbps của OVS | Tránh utilization sai 400 lần |

## 12. Review

TV1 review công thức, nguồn dữ liệu và chạy lại bài thử theo phiếu trong [qa/week1-review.md](../qa/week1-review.md#phiếu-review-n18-003--tv1-review-tv3).
