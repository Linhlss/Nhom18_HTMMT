#!/usr/bin/env python3
"""
Nhóm 18 — Hệ thống và Mạng máy tính (MI4060)
Module: workload/client.py (Task N18-006 & N18-014)
Vai trò: TV2 (Workload / UI Lead)

Client TCP gửi Request AI Inference giả lập từ c1 (10.18.1.10) hoặc c2 (10.18.2.10)
tới a1 (10.18.3.11:8000) hoặc a2 (10.18.3.12:8000), ghi log timestamp, payload size,
tách bạch server_service_ms khỏi net_rtt_est_ms, và tương thích hoàn toàn với:
    sudo /usr/bin/python3 control/networkctl.py exec --timeout 60 c1 -- /usr/bin/python3 workload/client.py
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import socket
import struct
import sys
import time
from typing import Dict, Any, Optional, List

HEADER_STRUCT = struct.Struct("!II")  # meta_len (4B), pad_len (4B)
HEADER_SIZE = HEADER_STRUCT.size      # 8 bytes
MAX_FRAME_BYTES = 16 * 1024 * 1024    # 16 MB safety cap

SERVER_ENDPOINTS: Dict[str, str] = {
    "a1": "10.18.3.11",
    "a2": "10.18.3.12",
    "localhost": "127.0.0.1",
}

IP_TO_HOST_NAME: Dict[str, str] = {
    "10.18.1.10": "c1",
    "10.18.2.10": "c2",
    "10.18.3.11": "a1",
    "10.18.3.12": "a2",
    "127.0.0.1": "localhost",
}

CSV_COLUMNS: List[str] = [
    "run_id",
    "config_id",
    "profile",
    "is_warmup",
    "flow_id",
    "client_host",
    "server_host",
    "src_port",
    "req_id",
    "send_ts_ns",
    "recv_ts_ns",
    "app_rtt_ms",
    "server_service_ms",
    "net_rtt_est_ms",
    "bytes_tx",
    "bytes_rx",
    "status",
]


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """Đọc chính xác num_bytes từ TCP socket để đảm bảo nhận trọn vẹn khung bản tin."""
    chunks: List[bytes] = []
    bytes_recd = 0
    while bytes_recd < num_bytes:
        chunk = sock.recv(min(num_bytes - bytes_recd, 65536))
        if not chunk:
            raise ConnectionError(
                f"Kết nối đóng sớm khi đang đọc ({bytes_recd}/{num_bytes} bytes)"
            )
        chunks.append(chunk)
        bytes_recd += len(chunk)
    return b"".join(chunks)


def build_framed_request(meta: Dict[str, Any], target_req_size: int) -> bytes:
    """Đóng gói bản tin Request có tổng kích thước đúng bằng target_req_size (>= 8 + meta_len)."""
    meta_bytes = json.dumps(meta, separators=(",", ":")).encode("utf-8")
    meta_len = len(meta_bytes)
    pad_len = max(0, int(target_req_size) - HEADER_SIZE - meta_len)
    header = HEADER_STRUCT.pack(meta_len, pad_len)
    if pad_len > 0:
        return header + meta_bytes + (b"X" * pad_len)
    return header + meta_bytes


def recv_framed_response(sock: socket.socket) -> tuple[Dict[str, Any], int]:
    """Nhận và giải mã bản tin Response từ Server."""
    header_bytes = recv_exact(sock, HEADER_SIZE)
    meta_len, pad_len = HEADER_STRUCT.unpack(header_bytes)
    total_payload = meta_len + pad_len
    if meta_len == 0 or total_payload > MAX_FRAME_BYTES:
        raise ValueError(f"Header phản hồi không hợp lệ: meta_len={meta_len}, pad_len={pad_len}")

    meta_bytes = recv_exact(sock, meta_len)
    if pad_len > 0:
        recv_exact(sock, pad_len)

    resp_meta = json.loads(meta_bytes.decode("utf-8"))
    total_rx_bytes = HEADER_SIZE + meta_len + pad_len
    return resp_meta, total_rx_bytes


def resolve_target_ip(target: str) -> str:
    return SERVER_ENDPOINTS.get(target, target)


def execute_flow(args: argparse.Namespace) -> tuple[List[Dict[str, Any]], int]:
    """Thực thi 1 luồng kết nối TCP từ Client tới Server trên cổng 8000."""
    target_ip = resolve_target_ip(args.target)
    target_port = args.port
    interval_sec = (1.0 / args.rate_rps) if args.rate_rps > 0 else 0.0
    timeout_sec = args.timeout_ms / 1000.0

    records: List[Dict[str, Any]] = []
    errors = 0

    try:
        with socket.create_connection((target_ip, target_port), timeout=timeout_sec) as sock:
            sock.settimeout(timeout_sec)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            local_ip, src_port = sock.getsockname()[:2]
            client_host = args.client_host or IP_TO_HOST_NAME.get(local_ip, local_ip)
            default_srv_host = IP_TO_HOST_NAME.get(target_ip, target_ip)

            flow_start_mono = time.perf_counter()
            seq = 0

            while True:
                elapsed_flow = time.perf_counter() - flow_start_mono
                if args.duration_sec > 0:
                    if elapsed_flow >= (args.warmup_sec + args.duration_sec):
                        break
                elif seq >= args.count:
                    break

                is_warmup = 1 if (args.duration_sec > 0 and elapsed_flow < args.warmup_sec) else 0
                req_id = f"{args.run_id}_f{args.flow_id}_r{seq}"
                req_loop_start = time.perf_counter()

                send_wall_ns = time.time_ns()
                req_meta = {
                    "req_id": req_id,
                    "run_id": args.run_id,
                    "flow_id": args.flow_id,
                    "client_host": client_host,
                    "seq": seq,
                    "client_send_ts_ns": send_wall_ns,
                    "resp_size_bytes": args.resp_size_bytes,
                    "service_delay_ms": args.service_delay_ms,
                }
                req_frame = build_framed_request(req_meta, args.req_size_bytes)
                bytes_tx = len(req_frame)

                send_mono_ns = time.perf_counter_ns()
                status = "OK"
                bytes_rx = 0
                srv_proc_ms = 0.0
                app_rtt_ms = 0.0
                net_rtt_est_ms = 0.0
                server_host = default_srv_host

                try:
                    sock.sendall(req_frame)
                    resp_meta, bytes_rx = recv_framed_response(sock)
                    recv_mono_ns = time.perf_counter_ns()
                    recv_wall_ns = time.time_ns()

                    app_rtt_ms = (recv_mono_ns - send_mono_ns) / 1e6
                    srv_proc_ms = float(resp_meta.get("server_proc_ms", 0.0))
                    net_rtt_est_ms = max(0.0, app_rtt_ms - srv_proc_ms)
                    server_host = str(resp_meta.get("server_host", default_srv_host))

                    if resp_meta.get("req_id") != req_id:
                        status = "MISMATCH_ID"
                        errors += 1
                    elif resp_meta.get("status") != "OK":
                        status = str(resp_meta.get("status", "SERVER_ERR"))
                        errors += 1
                except socket.timeout:
                    recv_wall_ns = time.time_ns()
                    status = "TIMEOUT"
                    errors += 1
                except OSError:
                    recv_wall_ns = time.time_ns()
                    status = "CONN_ERROR"
                    errors += 1

                record = {
                    "run_id": args.run_id,
                    "config_id": args.config_id,
                    "profile": args.profile,
                    "is_warmup": is_warmup,
                    "flow_id": args.flow_id,
                    "client_host": client_host,
                    "server_host": server_host,
                    "src_port": src_port,
                    "req_id": req_id,
                    "send_ts_ns": send_wall_ns,
                    "recv_ts_ns": recv_wall_ns,
                    "app_rtt_ms": round(app_rtt_ms, 3),
                    "server_service_ms": round(srv_proc_ms, 3),
                    "net_rtt_est_ms": round(net_rtt_est_ms, 3),
                    "bytes_tx": bytes_tx,
                    "bytes_rx": bytes_rx,
                    "status": status,
                }
                records.append(record)
                print(json.dumps(record, ensure_ascii=False), flush=True)

                seq += 1
                if status in ("TIMEOUT", "CONN_ERROR"):
                    break

                # Điều tiết tốc độ gửi (Pacing) khi gửi nhiều request
                if interval_sec > 0 and (args.duration_sec > 0 or seq < args.count):
                    spent = time.perf_counter() - req_loop_start
                    if spent < interval_sec:
                        time.sleep(interval_sec - spent)

    except OSError as exc:
        err_record = {
            "event": "client_connection_failed",
            "timestamp_ns": time.time_ns(),
            "target": f"{target_ip}:{target_port}",
            "error": str(exc),
        }
        print(json.dumps(err_record, ensure_ascii=False), file=sys.stderr, flush=True)
        return records, 1

    if args.csv_out and records:
        out_path = pathlib.Path(args.csv_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not out_path.exists()
        with out_path.open("a", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerows(records)

    return records, (0 if errors == 0 and len(records) > 0 else 1)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nhóm 18 TV2 — Client TCP gửi Request AI Inference tới a1/a2 cổng 8000"
    )
    parser.add_argument(
        "--target",
        default="10.18.3.11",
        help="Địa chỉ IP hoặc tên Server mục tiêu: a1 (10.18.3.11) hoặc a2 (10.18.3.12) (mặc định: 10.18.3.11)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Cổng TCP đích (mặc định: 8000 theo chính sách firewall fw)",
    )
    parser.add_argument(
        "--client-host",
        default=None,
        help="Tên Client host (c1 hoặc c2; tự động nhận diện từ IP nguồn nếu bỏ trống)",
    )
    parser.add_argument(
        "--run-id",
        default="w2_basic_run",
        help="Mã định danh lượt chạy (mặc định: w2_basic_run)",
    )
    parser.add_argument(
        "--config-id",
        default="cfg_w2_basic",
        help="Mã cấu hình workload (mặc định: cfg_w2_basic)",
    )
    parser.add_argument(
        "--profile",
        choices=["A", "B"],
        default="A",
        help="Nhãn Profile mạng hiện tại để ghi log (A hoặc B, mặc định: A)",
    )
    parser.add_argument(
        "--flow-id",
        type=int,
        default=0,
        help="Chỉ số flow_id của kết nối hiện tại (mặc định: 0)",
    )
    parser.add_argument(
        "--req-size-bytes",
        type=int,
        default=1024,
        help="Tổng kích thước bản tin Request tính bằng byte (mặc định: 1024)",
    )
    parser.add_argument(
        "--resp-size-bytes",
        type=int,
        default=65536,
        help="Tổng kích thước bản tin Response yêu cầu Server trả về (mặc định: 65536)",
    )
    parser.add_argument(
        "--service-delay-ms",
        type=float,
        default=5.0,
        help="Thời gian xử lý AI inference giả lập tại Server (ms, mặc định: 5.0)",
    )
    parser.add_argument(
        "--rate-rps",
        type=float,
        default=10.0,
        help="Tốc độ gửi mục tiêu trên flow (request/s, mặc định: 10.0)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Số lượng request cần gửi khi không đặt --duration-sec (mặc định: 1 cho bài test N18-006)",
    )
    parser.add_argument(
        "--warmup-sec",
        type=float,
        default=0.0,
        help="Thời gian warm-up ban đầu (giây, mặc định: 0.0)",
    )
    parser.add_argument(
        "--duration-sec",
        type=float,
        default=0.0,
        help="Nếu > 0, chạy liên tục theo thời gian thay vì theo --count (giây, mặc định: 0.0)",
    )
    parser.add_argument(
        "--timeout-ms",
        type=float,
        default=5000.0,
        help="Timeout cho kết nối và mỗi request (ms, mặc định: 5000.0)",
    )
    parser.add_argument(
        "--csv-out",
        default=None,
        help="Đường dẫn file CSV để lưu kết quả (ví dụ: results/raw/w2_basic.csv)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    _, exit_code = execute_flow(args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())