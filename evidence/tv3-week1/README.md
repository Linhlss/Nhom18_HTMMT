# Minh chứng TV3 tuần 1 — ping/iperf3 chẩn đoán và chuyển CSV (N18-003)

**Máy thực hiện:** VM `Nhom18-W1` (UTM, Ubuntu 24.04.5 ARM64, kernel 6.8.0-149-generic, iperf3 3.16-1build2, iputils-ping 20240117) trên Mac của TV1, testbed 10 node **profile A**. Lượt chạy do phiên hỗ trợ AI thực hiện theo yêu cầu của người dùng ngày 18/11/2026 — **không phải** TV3 chạy trên máy của TV3; TV3 cần tự chạy lại và giải thích.

**Đây là bài đo chẩn đoán**, không phải benchmark AI inference. Ping chạy trước, khi testbed không có tải; iperf3 chạy sau, riêng.

**Đặc tả:** [docs/metrics-spec.md](../../docs/metrics-spec.md).

## Lệnh tái lập

```bash
sudo /usr/bin/python3 control/networkctl.py start --profile A
sudo /usr/bin/python3 measurement/week1_probe.py --label tv3-probe
sudo /usr/bin/python3 control/networkctl.py stop
```

Lệnh đo bên trong: `ping -D -n -c 20 -i 0.2 -W 2 10.18.3.11` (c1); `iperf3 -s -1 -p 5201 -J` (a1); `iperf3 -c 10.18.3.11 -p 5201 -P 1 -t 10 -O 2 -J` (c1).

## Các lượt

| run_id | Commit | Công cụ | CSV | Ghi chú |
|---|---|---|---|---|
| [20261118T112753790043Z-tv3-probe](20261118T112753790043Z-tv3-probe/result.json) | `6d7df69` | đạt | **có lỗi F2** | Giữ nguyên làm lịch sử: `measured_seconds_from_intervals = 11.000318`, goodput interval min 13,63 Mbps lấy từ interval có thời gian sai |
| [20261118T112952839193Z-tv3-probe-rerun](20261118T112952839193Z-tv3-probe-rerun/result.json) | `af83849` | đạt | đạt | **Kết quả tuần 1** |

File mỗi lượt: raw `ping-c1-a1.txt`, `iperf3-c1-a1-client.json`, `iperf3-a1-server.json` (nguyên văn); `*-exec.json` (lệnh, mã thoát, stderr); CSV `ping-samples.csv`, `ping-summary.csv`, `iperf3-intervals.csv`, `iperf3-summary.csv`; `environment.json`, `network-status.json`, `source-manifest.json`, `result.json`, `exit-code.txt`.

## Kết quả lượt rerun

| Chỉ số | Giá trị |
|---|---|
| ICMP gửi/nhận, loss | 20/20, 0 % |
| `icmp_rtt_ms` n=20 nearest-rank | min 4,32; p50 4,49; p95 4,99; p99 = max 5,23 |
| ping tự báo min/avg/max/mdev | 4,321 / 4,560 / 5,234 / 0,208 ms |
| iperf3 goodput nhận / gửi | 23,872 / 23,909 Mbps; đo 9,999 s (sender) sau 2 s omit |
| TCP retransmits | 12 |

## Đối chiếu CSV ↔ raw (yêu cầu tối thiểu một RTT và một throughput)

- RTT: `ping-c1-a1.txt` dòng 2 `… icmp_seq=1 ttl=62 time=4.99 ms`, timestamp `[1795001392.918517]` ↔ `ping-samples.csv`: `icmp_seq=1`, `ts_utc=2026-11-18T11:29:52.918517Z`, `icmp_rtt_ms=4.99`, `raw_line=2`.
- Throughput: `iperf3-c1-a1-client.json` `end.sum_received.bits_per_second = 23871814.06135549` ↔ `iperf3-summary.csv` `receiver_goodput_mbps = 23.871814`.
- Checker TV4 so khớp toàn bộ 20 mẫu, số gói, nearest-rank, khoảng đo, tổng byte interval và SHA-256 raw.

## Phát hiện F1, F2

Xem [metrics-spec §9.3](../../docs/metrics-spec.md#93-phát-hiện-từ-kiểm-tra-log-và-cách-sửa) và [biên bản](../../qa/week1-review.md). Tóm tắt: F1 — sai số làm tròn của ping (kỳ vọng của checker sai, không phải lỗi CSV); F2 — iperf3 3.16 báo interval đầu sau `-O` với `seconds≈2,0` trái với `end−start`, converter cũ dùng sai. Đã sửa ở `af83849`, lượt rerun được kiểm tra lại đạt.
