# Minh chứng TV2 tuần 1 — bài thử request/response (N18-002)

**Máy thực hiện:** VM `Nhom18-W1` (UTM, Ubuntu 24.04.5 ARM64, kernel 6.8.0-149-generic, Python 3.12.3, Mininet 2.3.0-1.1, OVS 3.3.9) trên Mac của TV1. Bản clone `~/Nhom18_week1_tv234` trong VM, tạo từ Git bundle của nhánh `claude/complete-week1-n18-3fc6c1`. Lượt chạy do phiên hỗ trợ AI thực hiện theo yêu cầu của người dùng ngày 18/11/2026 — **không phải** TV2 chạy trên máy của TV2; TV2 cần tự chạy lại theo lệnh dưới đây và tự giải thích kết quả.

**Đặc tả:** [docs/workload-spec.md](../../docs/workload-spec.md). **Cấu hình:** [workload/configs/smoke-c1-a1.json](../../workload/configs/smoke-c1-a1.json) (`config_id=smoke_c1_a1_v1`).

## Lệnh tái lập

```bash
sudo /usr/bin/python3 control/networkctl.py start --profile A
sudo /usr/bin/python3 workload/smoke_test.py --label tv2-smoke --negative
sudo /usr/bin/python3 control/networkctl.py stop
```

## Các lượt

| run_id | Commit mã (source-manifest khớp) | Profile | Kết quả |
|---|---|---|---|
| [20261118T112728069663Z-tv2-smoke](20261118T112728069663Z-tv2-smoke/result.json) | `6d7df69` | A | **PASS** — 10/10 OK, client 0, server 0; 3/3 ca âm tính đúng mã |
| [20261118T113018044375Z-tv2-smoke-rerun](20261118T113018044375Z-tv2-smoke-rerun/result.json) | `af83849` | A | **PASS** — 10/10 OK, client 0, server 0; 3/3 ca âm tính đúng mã |

Cấu trúc mỗi lượt: `environment.json`, `network-status.json` (profile, session, config hash), `source-manifest.json`, `result.json`, `exit-code.txt`; thư mục `main/` và `neg-*/` mỗi ca có `exec-record.json` (lệnh, JSON trả về của `networkctl exec`), `client/client-requests.csv`, `client/client-summary.json`, `server/server-events.jsonl`, `server/server-summary.json`.

## Kết quả chính (dữ liệu đo, chỉ mô tả bài thử này)

| | Lượt 1 | Lượt rerun |
|---|---:|---:|
| Response hợp lệ | 10/10 | 10/10 |
| `req_bytes_sent` / `resp_bytes_received` | 1024 / 4096 mỗi request | 1024 / 4096 mỗi request |
| `app_response_ms` min–max (n=10) | 10,575 – 12,174 | 10,416 – 12,248 |
| `server_proc_ms` min–max (yêu cầu 5 ms) | 5,387 – 6,728 | 5,954 – 6,857 |
| `network_residual_est_ms` min–max, mẫu hợp lệ | 4,278 – 5,553 (10/10) | 4,281 – 5,731 (10/10) |
| Rate thực đạt / mục tiêu | 4,999 / 5,0 rps | 5,012 / 5,0 rps |
| p95 `send_lag_ms`, `load_sustained` | 4,908 ms, true | 4,803 ms, true |

## Ca âm tính (lỗi tạo có chủ đích)

| Ca | Lỗi đưa vào | Kỳ vọng | Lượt 1 | Rerun |
|---|---|---|---|---|
| `neg-wrong-id` | server đổi `req_id` của seq 3 thành `…-WRONG` | client mã 4, response lạ trong `unmatched_responses` | 4 ✔ | 4 ✔ |
| `neg-short-response` | server trả response seq 3 thiếu 100 byte | client mã 4, `SIZE_MISMATCH` | 4 ✔ | 4 ✔ |
| `neg-no-server` | không chạy server | client mã 3, `CONN_ERROR` | 3 ✔ | 3 ✔ |

Các ca này chứng minh client trả mã khác 0 khi sai ID/size hoặc lỗi kết nối; **không** được tính là kiểm thử kết nối đạt.

## Kiểm tra chéo

TV4 kiểm tra độc lập: [qa-report lần đầu](../tv4-week1/20261118T112845394713Z-tv4-logcheck/qa-report.md), [kiểm tra lại](../tv4-week1/20261118T113009015094Z-tv4-logcheck-recheck/qa-report.md). Phần TV2 đạt 13/13 ở cả hai lần. Review của TV3: [qa/week1-review.md](../../qa/week1-review.md).
