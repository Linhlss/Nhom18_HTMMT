# Kết quả kiểm tra log tuần 1 (TV4)

- Thời điểm chạy (UTC): 2026-11-18T11:30:09Z
- TV2 evidence: `evidence/tv2-week1/20261118T112728069663Z-tv2-smoke`
- TV3 evidence: `evidence/tv3-week1/20261118T112952839193Z-tv3-probe-rerun`
- Kết luận: **ĐẠT** (25/25 kiểm tra)

| Phần | Kiểm tra | Kết quả | Chi tiết |
|---|---|---|---|
| TV2 | result.json success=true và exit-code.txt=0 | ĐẠT | success=True |
| TV2 | client CSV có đúng 10 dòng, tất cả status=OK | ĐẠT | 10 dòng; status=['OK'] |
| TV2 | req_id duy nhất, seq liên tục 0..9, cùng run_id | ĐẠT | run_id=20261118T112728069663Z-tv2-smoke |
| TV2 | server ghi nhận 10 request, tập req_id trùng client | ĐẠT | 10 request event |
| TV2 | số byte request 1024 B và response 4096 B khớp ở cả client và server (frame gồm header+JSON+padding) | ĐẠT | config smoke_c1_a1_v1: 10/10 khớp |
| TV2 | server_proc_ms trong CSV client bằng log server | ĐẠT | 10/10 |
| TV2 | thứ tự UTC: client gửi ≤ server nhận ≤ client nhận (cùng đồng hồ VM) | ĐẠT | 10/10 |
| TV2 | network_residual_est_ms = app_response_ms − server_proc_ms, không âm, residual_valid=1 | ĐẠT | min=4.278180 ms |
| TV2 | CSV có đủ cột để tính metric theo metrics-spec §5 | ĐẠT | đủ |
| TV2 | profile/config_id tách riêng (profile=A, config_id=smoke_c1_a1_v1) | ĐẠT | profile=A, config_id=smoke_c1_a1_v1 |
| TV2 | negative control neg-wrong-id: client trả mã 4 và log đúng loại lỗi | ĐẠT | rc=4, status={'OK': 9, 'TIMEOUT': 1} |
| TV2 | negative control neg-short-response: client trả mã 4 và log đúng loại lỗi | ĐẠT | rc=4, status={'OK': 9, 'SIZE_MISMATCH': 1} |
| TV2 | negative control neg-no-server: client trả mã 3 và log đúng loại lỗi | ĐẠT | rc=3, status={'CONN_ERROR': 10} |
| TV3 | result.json success=true, profile A, exit-code 0 | ĐẠT | checks={'testbed_running_profile_A': True, 'ping_exit_0': True, 'iperf3_server_listening': True, 'iperf3_client_exit_0': True, 'iperf3_server_exit_0': True, 'ping_csv_ok': True, 'iperf3_csv_ok': True, 'ping_20_of_20': True} |
| TV3 | ping raw: 20 gói gửi/20 nhận, CSV packets_tx/rx khớp | ĐẠT | raw 20/20; CSV 20/20 |
| TV3 | từng mẫu RTT trong ping-samples.csv khớp dòng raw (seq, time) | ĐẠT | 20 mẫu CSV / 20 dòng raw; ví dụ seq=1 raw=4.99 ms, CSV=4.99 ms |
| TV3 | icmp_loss_pct tính từ gửi/nhận | ĐẠT | 0.0 % |
| TV3 | min/mean/max CSV khớp tổng kết ping trong sai số làm tròn mẫu (±0,005 ms) | ĐẠT | ping 4.321/4.56/5.234; CSV 4.32/4.562/5.23 |
| TV3 | p95/p99 nearest-rank tính lại khớp CSV (n=20) | ĐẠT | p95=4.99, p99=5.23, n=20 |
| TV3 | iperf3: TCP, 1 luồng, -t 10, -O 2, cổng 5201 | ĐẠT | protocol=TCP, streams=1, t=10, O=2 |
| TV3 | receiver goodput CSV = end.sum_received.bits_per_second/1e6 trong raw JSON | ĐẠT | raw=23.871814 Mbps; CSV=23.871814 |
| TV3 | khoảng đo (end.sum_sent.seconds) ≈ 10 s, không gồm 2 s omit; byte các interval đo = sum_sent.bytes | ĐẠT | 9.9993 s; 10 interval; 29884416 B |
| TV3 | interval có thời gian bất thường (seconds ≠ end−start) được đánh dấu timing_suspect | ĐẠT | raw: [0]; CSV: [0] |
| TV3 | raw ping-c1-a1.txt không bị sửa sau khi chuyển CSV (sha256) | ĐẠT | 992b892ebeb64659 |
| TV3 | raw iperf3-c1-a1-client.json không bị sửa sau khi chuyển CSV (sha256) | ĐẠT | fe0f3c4b0baf90c0 |
