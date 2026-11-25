#!/usr/bin/env python3
"""
Nhóm 18 — Hệ thống và Mạng máy tính (MI4060)
Module: tests/test_concurrency.py (Task N18-010)
Vai trò: TV2 (Workload / UI Lead)

Kiểm thử đơn vị và tích hợp cục bộ cho workload/runner.py:
  1. Xác minh kế hoạch phân luồng luân phiên giữa c1 và c2 cho các mức 1, 2, 4, 8 flows.
  2. Kiểm thử chạy song song 8 flows qua 2 client logic (c1, c2) tới server giả lập,
     xác minh đủ 8 source port riêng biệt, tổng số request, status == OK và duration > 0.
  3. Kiểm tra từ chối cấu hình concurrency không hợp lệ.
"""

from __future__ import annotations

import asyncio
import csv
import json
import pathlib
import socket
import sys
import tempfile
import threading
import unittest

# Tìm đường dẫn thư mục chứa server.py, client.py, runner.py
CURRENT_FILE = pathlib.Path(__file__).resolve()
REPO_ROOT = CURRENT_FILE.parent.parent
WORKLOAD_DIR = REPO_ROOT / "workload"
if (CURRENT_FILE.parent / "runner.py").exists():
    # Hỗ trợ chạy trực tiếp khi các file nằm cùng thư mục tạm
    WORKLOAD_DIR = CURRENT_FILE.parent

if str(WORKLOAD_DIR) not in sys.path:
    sys.path.insert(0, str(WORKLOAD_DIR))

import runner as wl_runner  # noqa: E402
import server as wl_server  # noqa: E402


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class LocalTestServerThread:
    """Chạy server.py trên thread nền phục vụ test end-to-end không cần Mininet."""

    def __init__(self, port: int, server_name: str, duration: float = 15.0) -> None:
        self.port = port
        self.server_name = server_name
        self.duration = duration
        self.emulator: wl_server.InferenceEmulatorServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        ready_evt = threading.Event()

        def _target() -> None:
            async def _serve() -> None:
                self.emulator = wl_server.InferenceEmulatorServer(
                    bind_host="127.0.0.1",
                    port=self.port,
                    server_name=self.server_name,
                    default_service_delay_ms=2.0,
                    default_resp_size_bytes=2048,
                    max_requests=0,
                )
                srv = await asyncio.start_server(
                    self.emulator.handle_client,
                    host="127.0.0.1",
                    port=self.port,
                    reuse_address=True,
                )
                ready_evt.set()
                async with srv:
                    try:
                        await asyncio.wait_for(
                            self.emulator.stop_event.wait(), timeout=self.duration
                        )
                    except asyncio.TimeoutError:
                        pass

            asyncio.run(_serve())

        self._thread = threading.Thread(target=_target, daemon=True)
        self._thread.start()
        if not ready_evt.wait(timeout=5.0):
            raise RuntimeError(f"Server {self.server_name} không khởi động kịp")

    def stop(self) -> None:
        if self.emulator is not None:
            # Báo dừng an toàn từ luồng chính
            self.emulator.stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


class TestConcurrencyRunner(unittest.TestCase):
    def test_alternating_plan_1_2_4_8_flows(self) -> None:
        """Kiểm tra phân bổ luân phiên c1/c2 cho 1, 2, 4, 8 flows."""
        expected_counts = {
            1: {"c1": 1, "c2": 0},
            2: {"c1": 1, "c2": 1},
            4: {"c1": 2, "c2": 2},
            8: {"c1": 4, "c2": 4},
        }
        for conc, exp in expected_counts.items():
            plan = wl_runner.build_flow_plan(conc, local_mode=False)
            self.assertEqual(len(plan), conc)
            c1_flows = [p for p in plan if p["client_host"] == "c1"]
            c2_flows = [p for p in plan if p["client_host"] == "c2"]
            self.assertEqual(len(c1_flows), exp["c1"])
            self.assertEqual(len(c2_flows), exp["c2"])
            if conc > 1:
                # Đảm bảo tính luân phiên c1, c2, c1, c2...
                for idx, item in enumerate(plan):
                    self.assertEqual(item["client_host"], "c1" if idx % 2 == 0 else "c2")

    def test_invalid_concurrency_raises(self) -> None:
        """Kiểm tra từ chối mức concurrency nằm ngoài {1, 2, 4, 8}."""
        for invalid in (0, 3, 6, 16):
            with self.assertRaises(ValueError):
                wl_runner.build_flow_plan(invalid)

    def test_eight_concurrent_flows_end_to_end(self) -> None:
        """Chạy thực tế 8 flows song song (4 trên c1, 4 trên c2) và kiểm tra log/CSV."""
        port_a1 = get_free_port()
        port_a2 = get_free_port()
        srv_a1 = LocalTestServerThread(port_a1, "a1")
        srv_a2 = LocalTestServerThread(port_a2, "a2")
        srv_a1.start()
        srv_a2.start()

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                csv_out = pathlib.Path(tmpdir) / "w3_8flows.csv"
                sum_out = pathlib.Path(tmpdir) / "w3_summary.json"
                args = wl_runner.parse_args(
                    [
                        "--mode",
                        "local",
                        "--concurrency",
                        "8",
                        "--profile",
                        "B",
                        "--run-id",
                        "test_w3_8flows",
                        "--req-size-bytes",
                        "512",
                        "--resp-size-bytes",
                        "4096",
                        "--service-delay-ms",
                        "2.0",
                        "--rate-rps",
                        "20.0",
                        "--count",
                        "3",
                        "--local-ports",
                        f"{port_a1},{port_a2}",
                        "--csv-out",
                        str(csv_out),
                        "--summary-out",
                        str(sum_out),
                    ]
                )
                plan = wl_runner.build_flow_plan(
                    args.concurrency, local_mode=True, local_ports=[port_a1, port_a2]
                )
                flow_results = wl_runner.orchestrate_local(plan, args)
                summary = wl_runner.save_outputs(flow_results, 0.5, args)

                self.assertEqual(summary["status"], "OK")
                self.assertEqual(summary["concurrency"], 8)
                self.assertEqual(summary["total_requests"], 24)  # 8 flows * 3 requests
                self.assertEqual(summary["ok_requests"], 24)
                self.assertEqual(summary["error_requests"], 0)
                self.assertEqual(len(summary["flows"]), 8)

                # Kiểm tra CSV đầu ra có đủ 8 flow_id và 8 src_port phân biệt
                with csv_out.open(encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual(len(rows), 24)
                self.assertEqual({int(r["flow_id"]) for r in rows}, set(range(8)))
                self.assertEqual({r["client_host"] for r in rows}, {"c1", "c2"})
                self.assertEqual(len({int(r["src_port"]) for r in rows}), 8)

                # Kiểm tra JSON summary ghi ra đĩa hợp lệ
                saved_summary = json.loads(sum_out.read_text(encoding="utf-8"))
                self.assertEqual(saved_summary["run_id"], "test_w3_8flows")
        finally:
            srv_a1.stop()
            srv_a2.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)