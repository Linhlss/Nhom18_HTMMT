#!/usr/bin/env python3
"""
Nhóm 18 — Hệ thống và Mạng máy tính (MI4060)
Module: tests/test_csv_parser_adapter.py (Gói TV2-R2-01 — Hạn 26/11)
Vai trò: TV2 (Workload / UI Lead)

Bộ kiểm thử hồi quy (regression tests) bằng unittest cho csv_parser_adapter.py:
  1. Đọc đúng schema hiện hành 30 cột (bắt buộc 9 cột cốt lõi) & từ chối cột cũ PR #12.
  2. Hỗ trợ trường có dấu phẩy trong dấu ngoặc kép (không dùng split(",")).
  3. Loại warmup hoàn toàn, KHÔNG fallback về toàn bộ dữ liệu khi chỉ có warmup.
  4. Giữ nguyên residual âm trong raw nhưng loại khỏi thống kê residual; tập rỗng -> "Chưa có dữ liệu".
  5. Phân vị nearest-rank: [1..10] -> P95 = 10; tập rỗng -> None (không trả 0).
  6. Goodput tách riêng chiều c2s (req_bytes_sent) và s2c (resp_bytes_received).
  7. Kiểm tra điều kiện ghép cặp A/B đầy đủ & chặn dữ liệu mô phỏng khỏi nghiệm thu.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

CURRENT_DIR = pathlib.Path(__file__).resolve().parent
for candidate in (CURRENT_DIR, CURRENT_DIR.parent / "backend" / "adapters"):
    if (candidate / "csv_parser_adapter.py").exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import csv_parser_adapter as adapter  # noqa: E402

HEADER_30 = (
    "run_id,config_id,profile,run_kind,is_warmup,flow_id,client_host,server_host,"
    "server_ip,server_port,src_port,req_id,seq,scheduled_send_mono_ns,send_mono_ns,"
    "recv_mono_ns,send_utc,recv_utc,send_lag_ms,req_bytes_sent,resp_bytes_expected,"
    "resp_bytes_received,app_response_ms,server_queue_ms,server_service_ms,"
    "server_proc_ms,network_residual_est_ms,residual_valid,status,error\n"
)


def make_row(
    *,
    is_warmup: int = 0,
    flow_id: int = 0,
    seq: int = 0,
    send_mono_ns: int = 1_000_000_000,
    recv_mono_ns: int = 1_011_360_000,
    send_lag_ms: float = 0.2,
    req_bytes: int = 2048,
    resp_bytes: int = 63488,
    app_ms: float = 11.36,
    srv_svc_ms: float = 5.0,
    srv_proc_ms: float = 5.1,
    residual_ms: float = 6.26,
    residual_valid: str = "true",
    status: str = "OK",
    error: str = "",
) -> str:
    return (
        f"run_real_01,cfg_v1,A,main,{is_warmup},{flow_id},c1,a1,10.18.3.11,8000,50100,"
        f"req_{seq},{seq},{send_mono_ns},{send_mono_ns},{recv_mono_ns},"
        f"2026-11-25T00:00:00Z,2026-11-25T00:00:00Z,{send_lag_ms},{req_bytes},{resp_bytes},"
        f"{resp_bytes},{app_ms},0.1,{srv_svc_ms},{srv_proc_ms},{residual_ms},{residual_valid},"
        f"{status},{error}\n"
    )


class TestCsvParserAdapterR201(unittest.TestCase):
    def _write_temp_csv(self, content: str) -> pathlib.Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        tmp.write(content)
        tmp.close()
        path = pathlib.Path(tmp.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    # 1. Schema & CSV Parsing
    def test_parse_current_schema_and_quoted_commas(self) -> None:
        csv_text = (
            HEADER_30
            + make_row(seq=0, app_ms=11.36, residual_ms=6.26, error='"note, with comma"')
            + make_row(seq=1, send_mono_ns=1_100_000_000, recv_mono_ns=2_000_000_000, app_ms=11.36, residual_ms=6.26)
        )
        p = self._write_temp_csv(csv_text)
        summary = adapter.parse_csv_file(p, window_duration_s=1.0)
        self.assertEqual(summary.measurement_rows, 2)
        self.assertAlmostEqual(summary.app_response_mean_ms, 11.36, places=2)
        self.assertAlmostEqual(summary.network_residual_est_mean_ms, 6.26, places=2)
        self.assertGreater(summary.goodput.resp_s2c_mbps, 0.0)
        self.assertGreater(summary.goodput.req_c2s_mbps, 0.0)

    def test_legacy_pr12_schema_rejected_explicitly(self) -> None:
        legacy_csv = (
            "run_id,config_id,profile,is_warmup,flow_id,app_rtt_ms,server_service_ms,"
            "net_rtt_est_ms,send_ts_ns,recv_ts_ns,bytes_tx,bytes_rx,status\n"
            "r1,c1,A,0,0,12.5,5.0,7.5,1000,2000,1024,4096,OK\n"
        )
        p = self._write_temp_csv(legacy_csv)
        with self.assertRaises(adapter.SchemaValidationError) as ctx:
            adapter.parse_csv_file(p)
        self.assertIn("app_response_ms", ctx.exception.missing_columns)
        self.assertIn("app_rtt_ms", ctx.exception.legacy_columns_detected)

    # 2. Warmup & Negative Residual
    def test_warmup_only_csv_no_fallback_returns_no_data(self) -> None:
        csv_text = HEADER_30 + make_row(is_warmup=1, seq=0, app_ms=50.0) + make_row(is_warmup=1, seq=1, app_ms=60.0)
        p = self._write_temp_csv(csv_text)
        summary = adapter.parse_csv_file(p)
        self.assertEqual(summary.total_raw_rows, 2)
        self.assertEqual(summary.warmup_rows_excluded, 2)
        self.assertEqual(summary.measurement_rows, 0)
        self.assertIsNone(summary.app_response_mean_ms)
        self.assertIsNone(summary.app_response_p95_ms)
        self.assertEqual(summary.to_report_dict()["metrics"]["app_response_mean_display"], adapter.EMPTY_DISPLAY)

    def test_negative_residual_kept_in_raw_excluded_from_stats(self) -> None:
        csv_text = (
            HEADER_30
            + make_row(seq=0, app_ms=10.0, residual_ms=-1.5, residual_valid="false")
            + make_row(seq=1, app_ms=12.0, residual_ms=4.0, residual_valid="true")
            + make_row(seq=2, app_ms=14.0, residual_ms=6.0, residual_valid="true")
        )
        p = self._write_temp_csv(csv_text)
        summary = adapter.parse_csv_file(p, window_duration_s=1.0)
        # Raw vẫn giữ đủ 3 dòng (kể cả dòng âm)
        self.assertEqual(len(summary.raw_rows), 3)
        self.assertEqual(summary.raw_rows[0].network_residual_est_ms, -1.5)
        # Thống kê residual chỉ tính trên 2 dòng dương hợp lệ (4.0 và 6.0)
        self.assertEqual(summary.residual_valid_rows, 2)
        self.assertEqual(summary.residual_excluded_rows, 1)
        self.assertAlmostEqual(summary.network_residual_est_mean_ms, 5.0, places=3)

    # 3. Nearest-Rank P95
    def test_p95_nearest_rank_1_to_10_returns_10(self) -> None:
        self.assertEqual(adapter.percentile_nearest_rank([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95), 10.0)
        self.assertEqual(adapter.percentile_nearest_rank([10, 3, 7, 1, 9, 2, 8, 4, 6, 5], 95), 10.0)
        self.assertIsNone(adapter.percentile_nearest_rank([], 95))
        self.assertEqual(adapter.format_metric(None, "ms"), adapter.EMPTY_DISPLAY)

    # 4. Directional Goodput
    def test_directional_goodput_not_summed(self) -> None:
        csv_text = HEADER_30 + make_row(seq=0, req_bytes=125_000, resp_bytes=1_250_000)
        p = self._write_temp_csv(csv_text)
        summary = adapter.parse_csv_file(p, window_duration_s=1.0)
        self.assertAlmostEqual(summary.goodput.req_c2s_mbps, 1.0, places=4)
        self.assertAlmostEqual(summary.goodput.resp_s2c_mbps, 10.0, places=4)

    # 5. Load sustained & A/B Pair Validation & Simulation Blocking
    def test_ab_pair_validation_rules(self) -> None:
        base_net = {"topology": "10node", "spine_mbps": 25.0, "delay_ms": 1.0}
        run_a = adapter.RunMetadata(
            run_id="runA", profile="A", config_id="cfg1", config_hash="abc123",
            network_condition=base_net, load_sustained=True,
            expected_window_s=30.0, actual_window_s=30.0,
            measurement_window_complete=True, sample_count=300, data_source="real",
        )
        run_b = adapter.RunMetadata(
            run_id="runB", profile="B", config_id="cfg1", config_hash="abc123",
            network_condition=base_net, load_sustained=True,
            expected_window_s=30.0, actual_window_s=30.0,
            measurement_window_complete=True, sample_count=300, data_source="real",
        )
        self.assertTrue(adapter.validate_ab_pair(run_a, run_b).is_valid)

        # Không đạt load_sustained ở lượt B -> phải từ chối
        run_b_unsustained = adapter.RunMetadata(**{**run_b.__dict__, "load_sustained": False})
        res1 = adapter.validate_ab_pair(run_a, run_b_unsustained)
        self.assertFalse(res1.is_valid)
        self.assertTrue(any("load_sustained" in r for r in res1.reasons))

        # Lệch config_hash -> phải từ chối
        run_b_diff_hash = adapter.RunMetadata(**{**run_b.__dict__, "config_hash": "zzz999"})
        res2 = adapter.validate_ab_pair(run_a, run_b_diff_hash)
        self.assertFalse(res2.is_valid)
        self.assertTrue(any("config_hash" in r for r in res2.reasons))

        # Dữ liệu mô phỏng -> bị chặn
        run_b_sim = adapter.RunMetadata(**{**run_b.__dict__, "data_source": "simulated"})
        res3 = adapter.validate_ab_pair(run_a, run_b_sim)
        self.assertFalse(res3.is_valid)


if __name__ == "__main__":
    unittest.main(verbosity=2)