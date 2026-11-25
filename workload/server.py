#!/usr/bin/env python3
"""
Nhóm 18 — Hệ thống và Mạng máy tính (MI4060)
Module: workload/server.py (Task N18-006 & N18-014)
Vai trò: TV2 (Workload / UI Lead)

Server TCP giả lập AI Inference lắng nghe trên cổng 8000 tại các host a1 (10.18.3.11)
và a2 (10.18.3.12) trong Mininet namespace, tương thích hoàn toàn với:
    sudo /usr/bin/python3 control/networkctl.py exec --timeout 120 a1 -- /usr/bin/python3 workload/server.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import socket
import struct
import sys
import time
from typing import Dict, Any, Optional

HEADER_STRUCT = struct.Struct("!II")  # meta_len (4B), pad_len (4B)
HEADER_SIZE = HEADER_STRUCT.size      # 8 bytes
MAX_FRAME_BYTES = 16 * 1024 * 1024    # Giới hạn an toàn 16 MB/frame

IP_TO_SERVER_NAME: Dict[str, str] = {
    "10.18.3.11": "a1",
    "10.18.3.12": "a2",
    "127.0.0.1": "localhost",
}


def resolve_server_name(local_ip: str, override_name: Optional[str]) -> str:
    if override_name:
        return override_name
    return IP_TO_SERVER_NAME.get(local_ip, local_ip)


async def read_framed_request(reader: asyncio.StreamReader) -> Optional[tuple[Dict[str, Any], int]]:
    """Đọc 1 khung bản tin Request theo định dạng 8-byte header + JSON metadata + binary padding."""
    try:
        header_bytes = await reader.readexactly(HEADER_SIZE)
    except asyncio.IncompleteReadError as exc:
        if len(exc.partial) == 0:
            return None  # Client đóng kết nối bình thường (EOF)
        raise ValueError(f"Header bị cắt cụt ({len(exc.partial)}/{HEADER_SIZE} bytes)") from exc

    meta_len, pad_len = HEADER_STRUCT.unpack(header_bytes)
    total_payload = meta_len + pad_len
    if meta_len == 0 or total_payload > MAX_FRAME_BYTES:
        raise ValueError(f"Kích thước khung không hợp lệ: meta_len={meta_len}, pad_len={pad_len}")

    meta_bytes = await reader.readexactly(meta_len)
    if pad_len > 0:
        await reader.readexactly(pad_len)

    meta = json.loads(meta_bytes.decode("utf-8"))
    total_rx_bytes = HEADER_SIZE + meta_len + pad_len
    return meta, total_rx_bytes


def build_framed_response(meta: Dict[str, Any], target_resp_size: int) -> bytes:
    """Đóng gói bản tin Response có tổng số byte đúng bằng target_resp_size (>= 8 + meta_len)."""
    meta_bytes = json.dumps(meta, separators=(",", ":")).encode("utf-8")
    meta_len = len(meta_bytes)
    pad_len = max(0, int(target_resp_size) - HEADER_SIZE - meta_len)
    header = HEADER_STRUCT.pack(meta_len, pad_len)
    if pad_len > 0:
        return header + meta_bytes + (b"R" * pad_len)
    return header + meta_bytes


class InferenceEmulatorServer:
    def __init__(
        self,
        bind_host: str,
        port: int,
        server_name: Optional[str],
        default_service_delay_ms: float,
        default_resp_size_bytes: int,
        max_requests: int,
    ) -> None:
        self.bind_host = bind_host
        self.port = port
        self.server_name_override = server_name
        self.default_service_delay_ms = default_service_delay_ms
        self.default_resp_size_bytes = default_resp_size_bytes
        self.max_requests = max_requests

        self.requests_served = 0
        self.bytes_received = 0
        self.bytes_sent = 0
        self.stop_event = asyncio.Event()

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        sockname = writer.get_extra_info("sockname")
        local_ip = sockname[0] if sockname else self.bind_host
        srv_name = resolve_server_name(local_ip, self.server_name_override)

        try:
            while not self.stop_event.is_set():
                framed = await read_framed_request(reader)
                if framed is None:
                    break

                req_meta, rx_bytes = framed
                server_recv_mono_ns = time.perf_counter_ns()
                server_recv_wall_ns = time.time_ns()

                req_id = str(req_meta.get("req_id", "unknown_req"))
                run_id = str(req_meta.get("run_id", "default_run"))
                flow_id = int(req_meta.get("flow_id", 0))
                service_delay_ms = float(
                    req_meta.get("service_delay_ms", self.default_service_delay_ms)
                )
                resp_size_bytes = int(
                    req_meta.get("resp_size_bytes", self.default_resp_size_bytes)
                )

                # Giả lập thời gian xử lý AI inference tại Server
                if service_delay_ms > 0.0:
                    await asyncio.sleep(service_delay_ms / 1000.0)

                server_send_mono_ns = time.perf_counter_ns()
                server_proc_ms = (server_send_mono_ns - server_recv_mono_ns) / 1e6

                resp_meta = {
                    "req_id": req_id,
                    "run_id": run_id,
                    "flow_id": flow_id,
                    "server_host": srv_name,
                    "server_recv_ts_ns": server_recv_mono_ns,
                    "server_send_ts_ns": server_send_mono_ns,
                    "server_proc_ms": round(server_proc_ms, 3),
                    "status": "OK",
                }
                resp_frame = build_framed_response(resp_meta, resp_size_bytes)
                tx_bytes = len(resp_frame)

                writer.write(resp_frame)
                await writer.drain()

                self.requests_served += 1
                self.bytes_received += rx_bytes
                self.bytes_sent += tx_bytes

                log_entry = {
                    "event": "request_handled",
                    "timestamp_ns": server_recv_wall_ns,
                    "server_host": srv_name,
                    "local_endpoint": f"{local_ip}:{self.port}",
                    "client_peer": f"{peer[0]}:{peer[1]}" if peer else "unknown",
                    "run_id": run_id,
                    "flow_id": flow_id,
                    "req_id": req_id,
                    "req_payload_bytes": rx_bytes,
                    "resp_payload_bytes": tx_bytes,
                    "server_proc_ms": round(server_proc_ms, 3),
                    "status": "OK",
                }
                print(json.dumps(log_entry, ensure_ascii=False), flush=True)

                if self.max_requests > 0 and self.requests_served >= self.max_requests:
                    self.stop_event.set()
                    break

        except Exception as exc:
            err_entry = {
                "event": "server_error",
                "timestamp_ns": time.time_ns(),
                "server_host": srv_name,
                "client_peer": f"{peer[0]}:{peer[1]}" if peer else "unknown",
                "error": str(exc),
            }
            print(json.dumps(err_entry, ensure_ascii=False), file=sys.stderr, flush=True)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


async def run_server(args: argparse.Namespace) -> int:
    emulator = InferenceEmulatorServer(
        bind_host=args.bind,
        port=args.port,
        server_name=args.server_host,
        default_service_delay_ms=args.service_delay_ms,
        default_resp_size_bytes=args.resp_size_bytes,
        max_requests=args.max_requests,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, emulator.stop_event.set)
        except NotImplementedError:
            pass

    server = await asyncio.start_server(
        emulator.handle_client,
        host=args.bind,
        port=args.port,
        reuse_address=True,
        backlog=128,
    )

    start_wall_ns = time.time_ns()
    start_info = {
        "event": "server_listening",
        "timestamp_ns": start_wall_ns,
        "bind": f"{args.bind}:{args.port}",
        "duration_sec": args.duration,
        "max_requests": args.max_requests,
    }
    print(json.dumps(start_info, ensure_ascii=False), flush=True)

    async with server:
        if args.duration > 0:
            try:
                await asyncio.wait_for(emulator.stop_event.wait(), timeout=args.duration)
            except asyncio.TimeoutError:
                pass
        else:
            await emulator.stop_event.wait()

    summary = {
        "event": "server_stopped",
        "timestamp_ns": time.time_ns(),
        "requests_served": emulator.requests_served,
        "total_bytes_rx": emulator.bytes_received,
        "total_bytes_tx": emulator.bytes_sent,
    }
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nhóm 18 TV2 — Server TCP giả lập AI Inference trên cổng 8000"
    )
    parser.add_argument(
        "--bind",
        default="0.0.0.0",
        help="Địa chỉ IP lắng nghe (mặc định: 0.0.0.0 để nhận trên 10.18.3.11 / 10.18.3.12)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Cổng TCP lắng nghe (mặc định: 8000 theo cấu hình firewall fw)",
    )
    parser.add_argument(
        "--server-host",
        default=None,
        help="Tên định danh server (a1 hoặc a2; tự động nhận diện theo IP nếu bỏ trống)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=25.0,
        help=(
            "Thời gian lắng nghe tối đa (giây) trước khi tự thoát với mã 0 để "
            "networkctl.py exec không bị timeout (mặc định: 25s, đặt 0 để chạy vô hạn)"
        ),
    )
    parser.add_argument(
        "--max-requests",
        type=int,
        default=0,
        help="Dừng server ngay sau khi phục vụ đủ N request (0 = không giới hạn theo số request)",
    )
    parser.add_argument(
        "--service-delay-ms",
        type=float,
        default=5.0,
        help="Thời gian xử lý giả lập mặc định nếu request không chỉ định (ms, mặc định: 5.0)",
    )
    parser.add_argument(
        "--resp-size-bytes",
        type=int,
        default=65536,
        help="Kích thước bản tin Response mặc định nếu request không chỉ định (bytes, mặc định: 65536)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    try:
        return asyncio.run(run_server(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())