# Biên bản review chéo và kiểm tra tuần 1 (N18-002, N18-003, N18-004)

| Mục | Nội dung |
|---|---|
| Ngày lập | 18/11/2026 (UTC log 11:27–11:31) |
| Người lập | TV4 (đầu mối QA). **Dự thảo** do phiên hỗ trợ AI (Claude Code) soạn theo yêu cầu của người dùng; các mục chữ ký do thành viên tự điền |
| Nhánh / commit được kiểm tra | `claude/complete-week1-n18-3fc6c1`: mã `6d7df69` (lượt đầu), `af83849` (sau sửa F1/F2); tài liệu v1.0 trong cùng nhánh |
| Bản nháp v0 được review (ngoài repo, thư mục “Sản phẩm của 3 thành viên còn lại”) | `Workload Spec.pdf` sha256 `d9d7af2b…f7ba0`; `Báo cáo Đặc tả Metrics … W1.pdf` sha256 `59a5ced7…45348`; `Tiến_độ_final_hệ_thống_mạng.pdf` sha256 `00b03338…a121d` |
| Môi trường chạy | VM `Nhom18-W1`, UTM, Ubuntu 24.04.5 ARM64, kernel 6.8.0-149-generic, trên Mac của TV1; testbed profile A, session `3a3beeff190934dd` |

> **Lưu ý:** các bài thử được chạy trên VM của TV1 bởi phiên hỗ trợ AI. Review của thành viên được thực hiện ngoài repository; kết luận “Đạt” bên dưới được ghi theo xác nhận của nhóm trưởng TV1 ngày 18/11/2026.

## 1. Phân công và kết quả

| Task | Người thực hiện | Sản phẩm | Reviewer | Nội dung review | Kiểm tra tự động | Kết luận reviewer |
|---|---|---|---|---|---|---|
| N18-002 | TV2 | [workload-spec.md](../docs/workload-spec.md), `workload/`, [evidence](../evidence/tv2-week1/README.md) | **TV3** | Schema, cách ghi thời gian, khả năng dùng log tính metric | Checker TV4: 13/13 đạt (cả hai lần) | ☑ Đạt — TV3 (theo xác nhận của nhóm trưởng TV1 ngày 18/11/2026) |
| N18-003 | TV3 | [metrics-spec.md](../docs/metrics-spec.md), `measurement/`, [evidence](../evidence/tv3-week1/README.md) | **TV1** | Công thức, nguồn dữ liệu, **chạy lại bài thử** | Lần đầu 9/11 (F1, F2) → sau sửa 12/12 | ☑ Đạt — TV1 (theo xác nhận của nhóm trưởng TV1 ngày 18/11/2026) |
| N18-004 | TV4 | [scope-rubric.md](../docs/scope-rubric.md), `qa/`, [evidence](../evidence/tv4-week1/README.md), [issue drafts](issues/) | **TV2** (rõ ràng, kiểm thử được); **TV1 phê duyệt** | Rubric E01–E10, quy ước, phạm vi | — | TV2: ☑ Đạt · TV1: ☑ Phê duyệt (theo xác nhận của nhóm trưởng TV1 ngày 18/11/2026) |

## 2. Phát hiện khi review bản nháp v0 (đã sửa trong v1.0)

Mức **B** = bắt buộc sửa trước khi đóng tuần; **K** = khuyến nghị.

| ID | Tài liệu | Phát hiện | Mức | Xử lý trong v1.0 |
|---|---|---|---|---|
| R01 | Workload | Bảng schema `clients: list[string]`, `servers: ["ip:port"]` nhưng ví dụ YAML dùng object `name/ip(/port)` | B | Thống nhất object; validator từ chối dạng chuỗi (`tests/test_workload.py`) |
| R02 | Workload | `protocol: "tcp" \| "http"` dù HTTP chưa có framing/đặc tả | B | Chỉ `tcp-binary-v1` cổng 8000; HTTP là mở rộng |
| R03 | Workload | `req/resp_size_bytes ≥ 128` nhỏ hơn header 8 B + metadata (đo được tối thiểu 474/529 B) | B | Size = tổng frame; ngưỡng tính từ mã; thiếu chỗ báo lỗi |
| R04 | Workload | Không nói rate là open/closed loop; không phân biệt rate mục tiêu/thực đạt | B | Open loop, `load_sustained`, cấm ghép cặp A/B khi không duy trì tải |
| R05 | Workload | `app_rtt_ms`; `net_rtt_est_ms = max(0, …)` gọi “độ trễ mạng thuần túy” | B | `app_response_ms`, `network_residual_est_ms`; mẫu âm `residual_valid=0`, không ép 0 |
| R06 | Workload | Offered load cộng request + response trên link full-duplex | K | Tính riêng từng chiều |
| R07 | Workload | `send_ts_ns`/`recv_ts_ns` không nói đồng hồ; server ghi `perf_counter_ns` | K | `*_utc` để đối chiếu, `*_mono_ns` để tính khoảng |
| R08 | Metrics | `rtt_avg/p95/p99` dùng chung cho ping và ứng dụng | B | Tách 4 chỉ số thời gian |
| R09 | Metrics | Throughput iperf3 và counter OVS coi như một | B | Tách goodput và throughput interface |
| R10 | Metrics | `utilization_pct` một chiều | B | `tx_util_pct`, `rx_util_pct`, tổng hợp `max` |
| R11 | Metrics | `packet_loss_pct` lấy từ drop counter | B | Loss chỉ từ ICMP gửi/nhận; drop là số gói delta |
| R12 | Metrics | `config_id` mô tả là “A/B” | B | `config_id` ≠ `profile` |
| R13 | Metrics | Không có quy tắc warm-up, counter reset, thiếu dữ liệu; p95/p99 không nói cách tính | B | §3–5 metrics-spec |
| R14 | Metrics | Capacity “do TV1 cung cấp” — dễ dùng nhầm speed 10 Gbps của veth | K | Lấy rate HTB từ `tc` |
| R15 | Scope | Ngân hàng X, 3.000 nhân viên, GPU 40 % viết như sự kiện | B | Ghi “giả định minh họa” |
| R16 | Scope | Thiếu rubric E01–E10 (người phụ trách, bằng chứng, reviewer, điều kiện đạt), quy ước, board | B | scope-rubric §4, §6 |
| R17 | Scope | “Server emulator không chạy LLM, nên RTT đo được là của mạng” | B | Tách `server_proc_ms`/`network_residual_est_ms` |
| R18 | Scope | “Độ dao động thấp” đặt làm bằng chứng E09 | K | Báo cáo độ dao động (E08); E09 là tái lập |

## 3. Phát hiện khi kiểm tra log (bài thử TV4)

| ID | Lượt / bằng chứng | Phát hiện | Nguyên nhân | Sửa (commit) | Kiểm tra lại |
|---|---|---|---|---|---|
| F1 | [qa-report lần đầu](../evidence/tv4-week1/20261118T112845394713Z-tv4-logcheck/qa-report.md), TV3 `…112753…-tv3-probe` | CSV min 4,26 / mean 4,493 ms ≠ ping 4,256 / 4,491 ms; kiểm tra so bằng tuyệt đối → KHÔNG ĐẠT | ping in từng reply 3 chữ số có nghĩa, tổng kết tính từ giá trị chưa làm tròn. **Checker kỳ vọng sai**, CSV đúng | `af83849`: dung sai ±0,005 ms; ghi vào metrics-spec §5.3 | [Recheck](../evidence/tv4-week1/20261118T113009015094Z-tv4-logcheck-recheck/qa-report.md) ĐẠT |
| F2 | như trên | `measured_seconds_from_intervals = 11.0003` thay vì ~10 s; goodput interval min 13,63 Mbps | iperf3 3.16 báo interval đầu sau `-O` với `seconds = 2,0007` nhưng `end − start ≈ 0,001`; converter cộng `seconds`. Lặp lại ở lượt rerun (interval 1 `seconds = 2,0079`) | `af83849`: dùng `end.sum_*`, cột `timing_suspect`, loại khỏi min/max, đối chiếu byte với `sum_sent` | Recheck ĐẠT; lượt rerun `timing_suspect_intervals=1`, min 19,84 Mbps |

TV2 không có phát hiện ở lần kiểm tra log: 10/10 request khớp ID, 1024/4096 byte ở cả hai phía, `server_proc_ms` khớp log server, thứ tự UTC hợp lệ, residual không âm; 3 ca âm tính trả đúng mã.

## Phiếu review N18-002 — TV3 review TV2

- [ ] Bảng schema (§3.1) và hai file cấu hình mẫu giống nhau; `python3 workload/config.py workload/configs/*.json` trả 0.
- [ ] Hiểu và đồng ý định nghĩa size = tổng frame (header + JSON + padding); thử đặt `req_size_bytes: 128` thấy báo lỗi.
- [ ] Ngữ nghĩa rate open loop và quy tắc `load_sustained` đủ để TV3 loại lượt không đạt tải khi so sánh A/B.
- [ ] `*_utc` vs `*_mono_ns` dùng đúng; `app_response_ms`, `server_proc_ms`, `network_residual_est_ms`, `residual_valid` đủ để tính metric theo metrics-spec §2, §5.
- [ ] Mở `client-requests.csv` của một lượt, tự tính lại `network_residual_est_ms` cho một dòng.
- [ ] Kết luận và yêu cầu sửa (nếu có): ………

## Phiếu review N18-003 — TV1 review TV3

- [ ] Công thức §2 đúng đơn vị; utilization dùng capacity HTB; loss/drop/retransmit tách đúng.
- [ ] Quy tắc warm-up, counter reset, `value_status`, nearest-rank (§3–5) dùng được cho N18-011/019.
- [ ] **Chạy lại** `sudo /usr/bin/python3 measurement/week1_probe.py --label tv1-review` trên profile A; ghi run_id: ……… ; kết quả: ………
- [ ] Chạy `python3 qa/check_week1_logs.py --tv2 … --tv3 <run của TV1> --out …` và đính kèm kết quả.
- [ ] Đồng ý cách xử lý F1, F2.
- [ ] Kết luận: ………

## Phiếu review N18-004 — TV2 review, TV1 phê duyệt

- [ ] (TV2) Mỗi E01–E10 có chủ trì, bằng chứng, reviewer, điều kiện đạt kiểm thử được bằng lệnh/file cụ thể.
- [ ] (TV2) Quy ước tên run/file, đơn vị, thư mục minh chứng, PR, trạng thái rõ ràng; checker chạy được trên máy TV2.
- [ ] (TV1) Phê duyệt phạm vi P0/P1/ngoài phạm vi và rubric E01–E10.
- [ ] (TV1) Xác nhận board/issue N18-002/003/004 đã tạo hoặc giao người tạo.
- [ ] Kết luận: ………

## 4. Kết quả đóng tuần 1

1. Review của TV3 (N18-002), TV1 (N18-003), TV2 (N18-004) và phê duyệt của TV1 cho phạm vi/rubric: **đạt** (theo xác nhận của nhóm trưởng TV1 ngày 18/11/2026).
2. Tracker: N18-002/003/004 và 9 task hạ tầng TV1 (N18-005/009/013/017/021/025/029/033/037) chuyển **Hoàn thành**; E01, E02, E07 **Hoàn thành**. **G1 đã chốt.**
3. Đã tạo 3 issue trên GitHub (Linhlss/Nhom18_HTMMT #1–#3) và PR #4. Board GitHub Projects còn chờ token có scope `project`.
4. Việc tiếp theo không chặn G1: mỗi thành viên chạy lại bài thử tuần 1 trên máy của mình để kiểm tra tái lập (thuộc E09).
