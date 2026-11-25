#!/usr/bin/env python3
"""
Nhóm 18 — Hệ thống và Mạng máy tính (MI4060)
Module: backend/adapters/csv_parser_adapter.py (Gói TV2-R2-01 — N18-014/018/030)
Vai trò: TV2 (Workload / UI Lead)

Parser CSV & bộ kiểm định thống kê đúng chuẩn đặc tả docs/workload-spec.md
và docs/metrics-spec.md trên nhánh main của Nhom18_HTMMT:
  - Dùng csv.DictReader chuẩn (hỗ trợ trường có dấu phẩy trong dấu ngoặc kép).
  - Bắt buộc đúng schema 9 cột đo hiện hành (từ chối tường minh schema cũ PR #12).
  - Loại warmup khỏi thống kê, KHÔNG fallback về toàn bộ dữ liệu khi chỉ có warmup.
  - Giữ nguyên residual âm ở tập raw nhưng loại khỏi thống kê residual.
  - Phân vị nearest-rank: rank = ceil((p / 100) * n); [1..10] cho P95 = 10; tập rỗng -> None ("Chưa có dữ liệu").
  - Goodput tính riêng từng chiều (c2s từ req_bytes_sent, s2c từ resp_bytes_received).
  - Kiểm tra đầy đủ điều kiện ghép cặp A/B và chặn dữ liệu mô phỏng khỏi kết quả nghiệm thu.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import statistics
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

EMPTY_DISPLAY = "Chưa có dữ liệu"

REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "app_response_ms",
        "server_proc_ms",
        "server_service_ms",
        "network_residual_est_ms",
        "residual_valid",
        "send_mono_ns",
        "recv_mono_ns",
        "req_bytes_sent",
        "resp_bytes_received",
    }
)

LEGACY_PR12_COLUMNS: frozenset[str] = frozenset(
    {
        "app_rtt_ms",
        "net_rtt_est_ms",
        "send_ts_ns",
        "recv_ts_ns",
        "bytes_tx",
        "bytes_rx",
    }
)


class SchemaValidationError(ValueError):
    """Ném ra khi tệp CSV thiếu cột bắt buộc hoặc dùng tên cột cũ của PR #12."""

    def __init__(
        self,
        message: str,
        missing_columns: Sequence[str] = (),
        legacy_columns_detected: Sequence[str] = (),
    ) -> None:
        super().__init__(message)
        self.missing_columns = list(missing_columns)
        self.legacy_columns_detected = list(legacy_columns_detected)


class SimulationExportError(ValueError):
    """Ném ra khi cố xuất hoặc đối chứng dữ liệu mô phỏng thành kết quả nghiệm thu."""


@dataclass
class ParsedSample:
    app_response_ms: Optional[float]
    server_proc_ms: Optional[float]
    server_service_ms: Optional[float]
    network_residual_est_ms: Optional[float]
    residual_valid: bool
    send_mono_ns: Optional[int]
    recv_mono_ns: Optional[int]
    req_bytes_sent: Optional[int]
    resp_bytes_received: Optional[int]
    is_warmup: bool
    flow_id: Optional[int]
    send_lag_ms: Optional[float]
    status: str
    raw_row: Dict[str, str]


@dataclass
class DirectionalGoodput:
    req_c2s_mbps: Optional[float]
    resp_s2c_mbps: Optional[float]
    window_duration_s: Optional[float]
    req_bytes_total: int
    resp_bytes_total: int

    def to_display_dict(self) -> Dict[str, Any]:
        return {
            "req_c2s_mbps": self.req_c2s_mbps,
            "req_c2s_display": format_metric(self.req_c2s_mbps, "Mbps"),
            "resp_s2c_mbps": self.resp_s2c_mbps,
            "resp_s2c_display": format_metric(self.resp_s2c_mbps, "Mbps"),
            "window_duration_s": self.window_duration_s,
            "req_bytes_total": self.req_bytes_total,
            "resp_bytes_total": self.resp_bytes_total,
        }


@dataclass
class ParsedCsvSummary:
    run_id: str
    data_source: str
    total_raw_rows: int
    warmup_rows_excluded: int
    measurement_rows: int
    ok_measurement_rows: int
    residual_valid_rows: int
    residual_excluded_rows: int
    app_response_mean_ms: Optional[float]
    app_response_p50_ms: Optional[float]
    app_response_p95_ms: Optional[float]
    server_proc_mean_ms: Optional[float]
    server_service_mean_ms: Optional[float]
    network_residual_est_mean_ms: Optional[float]
    network_residual_est_p50_ms: Optional[float]
    network_residual_est_p95_ms: Optional[float]
    goodput: DirectionalGoodput
    raw_rows: List[ParsedSample] = field(default_factory=list, repr=False)

    def to_report_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "data_source": self.data_source,
            "counts": {
                "total_raw_rows": self.total_raw_rows,
                "warmup_rows_excluded": self.warmup_rows_excluded,
                "measurement_rows": self.measurement_rows,
                "ok_measurement_rows": self.ok_measurement_rows,
                "residual_valid_rows": self.residual_valid_rows,
                "residual_excluded_rows": self.residual_excluded_rows,
            },
            "metrics": {
                "app_response_mean_ms": self.app_response_mean_ms,
                "app_response_mean_display": format_metric(self.app_response_mean_ms, "ms"),
                "app_response_p50_ms": self.app_response_p50_ms,
                "app_response_p50_display": format_metric(self.app_response_p50_ms, "ms"),
                "app_response_p95_ms": self.app_response_p95_ms,
                "app_response_p95_display": format_metric(self.app_response_p95_ms, "ms"),
                "server_proc_mean_ms": self.server_proc_mean_ms,
                "server_service_mean_ms": self.server_service_mean_ms,
                "network_residual_est_mean_ms": self.network_residual_est_mean_ms,
                "network_residual_est_mean_display": format_metric(
                    self.network_residual_est_mean_ms, "ms"
                ),
                "network_residual_est_p50_ms": self.network_residual_est_p50_ms,
                "network_residual_est_p95_ms": self.network_residual_est_p95_ms,
                "network_residual_est_p95_display": format_metric(
                    self.network_residual_est_p95_ms, "ms"
                ),
                "goodput": self.goodput.to_display_dict(),
            },
        }


@dataclass
class RunMetadata:
    run_id: str
    profile: str
    config_id: str
    config_hash: str
    network_condition: Dict[str, Any]
    load_sustained: Optional[bool]
    expected_window_s: float
    actual_window_s: float
    measurement_window_complete: bool
    sample_count: int
    data_source: str = "real"


@dataclass
class PairValidationResult:
    is_valid: bool
    reasons: List[str]
    run_a_id: str
    run_b_id: str
    sample_counts: Dict[str, int]


def _parse_float(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        val = float(text)
    except ValueError:
        return None
    if math.isnan(val) or math.isinf(val):
        return None
    return val


def _parse_int(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _parse_bool(raw: Optional[str], default: bool = False) -> bool:
    if raw is None:
        return default
    text = raw.strip().lower()
    if text in ("1", "true", "yes", "y"):
        return True
    if text in ("0", "false", "no", "n", ""):
        return False
    return default


def format_metric(value: Optional[float], unit: str = "", decimals: int = 3) -> str:
    if value is None:
        return EMPTY_DISPLAY
    suffix = f" {unit}" if unit else ""
    return f"{value:.{decimals}f}{suffix}"


def percentile_nearest_rank(values: Sequence[float], p: float) -> Optional[float]:
    """
    Tính phân vị theo định nghĩa nearest-rank (docs/metrics-spec.md §5.1):
        rank = ceil((p / 100) * n)  (1-based)
    - Với [1..10] và p=95 -> rank = ceil(9.5) = 10 -> trả về 10.
    - Tập rỗng -> trả về None (không trả về 0).
    """
    if not values:
        return None
    if p <= 0 or p > 100:
        raise ValueError(f"Phân vị p phải nằm trong (0, 100], nhận được: {p}")

    ordered = sorted(values)
    n = len(ordered)
    if float(p).is_integer():
        rank = (int(p) * n + 99) // 100
    else:
        rank = math.ceil((p / 100.0) * n)
    rank = max(1, min(n, rank))
    return float(ordered[rank - 1])


def load_csv_samples(
    csv_path: pathlib.Path,
    measurement_start_ns: Optional[int] = None,
) -> tuple[List[ParsedSample], str]:
    """
    Đọc file client-requests.csv bằng csv.DictReader chuẩn (hỗ trợ dấu phẩy trong ngoặc kép).
    Kiểm tra đầy đủ 9 cột bắt buộc và ném SchemaValidationError rõ ràng nếu thiếu cột.
    """
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SchemaValidationError(
                f"Tệp CSV rỗng hoặc không có dòng tiêu đề: {csv_path}",
                missing_columns=sorted(REQUIRED_COLUMNS),
            )

        cleaned_fields = [name.strip() for name in reader.fieldnames if name is not None]
        reader.fieldnames = cleaned_fields
        field_set = set(cleaned_fields)

        missing = sorted(REQUIRED_COLUMNS - field_set)
        legacy_found = sorted(LEGACY_PR12_COLUMNS & field_set)
        if missing:
            hint = (
                f" (phát hiện cột cũ PR #12: {', '.join(legacy_found)})"
                if legacy_found
                else ""
            )
            raise SchemaValidationError(
                f"Schema CSV không được hỗ trợ — thiếu cột bắt buộc: {', '.join(missing)}{hint}",
                missing_columns=missing,
                legacy_columns_detected=legacy_found,
            )

        samples: List[ParsedSample] = []
        detected_run_id = csv_path.stem
        for raw_row in reader:
            norm_row = {
                (k.strip() if k else ""): (v if v is not None else "")
                for k, v in raw_row.items()
            }
            if norm_row.get("run_id", "").strip():
                detected_run_id = norm_row["run_id"].strip()

            send_mono_ns = _parse_int(norm_row.get("send_mono_ns"))
            is_warmup_flag = _parse_bool(norm_row.get("is_warmup"), default=False)
            if not is_warmup_flag and norm_row.get("phase", "").strip().lower() == "warmup":
                is_warmup_flag = True
            if (
                not is_warmup_flag
                and measurement_start_ns is not None
                and send_mono_ns is not None
                and send_mono_ns < measurement_start_ns
            ):
                is_warmup_flag = True

            samples.append(
                ParsedSample(
                    app_response_ms=_parse_float(norm_row.get("app_response_ms")),
                    server_proc_ms=_parse_float(norm_row.get("server_proc_ms")),
                    server_service_ms=_parse_float(norm_row.get("server_service_ms")),
                    network_residual_est_ms=_parse_float(norm_row.get("network_residual_est_ms")),
                    residual_valid=_parse_bool(norm_row.get("residual_valid"), default=False),
                    send_mono_ns=send_mono_ns,
                    recv_mono_ns=_parse_int(norm_row.get("recv_mono_ns")),
                    req_bytes_sent=_parse_int(norm_row.get("req_bytes_sent")),
                    resp_bytes_received=_parse_int(norm_row.get("resp_bytes_received")),
                    is_warmup=is_warmup_flag,
                    flow_id=_parse_int(norm_row.get("flow_id")),
                    send_lag_ms=_parse_float(norm_row.get("send_lag_ms")),
                    status=norm_row.get("status", "OK").strip() or "OK",
                    raw_row=norm_row,
                )
            )
    return samples, detected_run_id


def compute_directional_goodput(
    measurement_samples: Sequence[ParsedSample],
    window_duration_s: Optional[float] = None,
) -> DirectionalGoodput:
    """
    Tính goodput RIÊNG TỪNG CHIỀU theo docs/metrics-spec.md §2:
      - c2s (client -> server): sum(req_bytes_sent) * 8 / (T * 1e6)
      - s2c (server -> client): sum(resp_bytes_received) * 8 / (T * 1e6)
    Tuyệt đối KHÔNG cộng gộp req + resp để so với capacity một chiều.
    """
    ok_samples = [s for s in measurement_samples if s.status == "OK"]
    req_total = sum(s.req_bytes_sent for s in ok_samples if s.req_bytes_sent is not None)
    resp_total = sum(s.resp_bytes_received for s in ok_samples if s.resp_bytes_received is not None)

    dur_s = window_duration_s
    if dur_s is None and measurement_samples:
        send_vals = [s.send_mono_ns for s in measurement_samples if s.send_mono_ns is not None]
        recv_vals = [s.recv_mono_ns for s in measurement_samples if s.recv_mono_ns is not None]
        if send_vals and recv_vals:
            delta_ns = max(recv_vals) - min(send_vals)
            dur_s = (delta_ns / 1e9) if delta_ns > 0 else None

    if not ok_samples or dur_s is None or dur_s <= 0:
        return DirectionalGoodput(
            req_c2s_mbps=None,
            resp_s2c_mbps=None,
            window_duration_s=dur_s if (dur_s is not None and dur_s > 0) else None,
            req_bytes_total=req_total,
            resp_bytes_total=resp_total,
        )

    return DirectionalGoodput(
        req_c2s_mbps=round((req_total * 8.0) / (dur_s * 1_000_000.0), 6),
        resp_s2c_mbps=round((resp_total * 8.0) / (dur_s * 1_000_000.0), 6),
        window_duration_s=round(dur_s, 6),
        req_bytes_total=req_total,
        resp_bytes_total=resp_total,
    )


def summarize_samples(
    samples: Sequence[ParsedSample],
    run_id: str,
    data_source: str = "real",
    window_duration_s: Optional[float] = None,
) -> ParsedCsvSummary:
    """
    Tổng hợp thống kê từ tập bản ghi đã đọc:
      - Loại warmup hoàn toàn; KHÔNG fallback về toàn bộ tập khi chỉ có warmup.
      - Giữ nguyên bản ghi residual âm trong raw_rows nhưng loại khỏi thống kê residual.
      - Không gọi phần dư ước lượng là "RTT mạng thuần túy".
    """
    raw_list = list(samples)
    measurement_list = [s for s in raw_list if not s.is_warmup]
    warmup_excluded = len(raw_list) - len(measurement_list)

    ok_meas = [s for s in measurement_list if s.status == "OK"]
    app_vals = [s.app_response_ms for s in ok_meas if s.app_response_ms is not None]
    srv_proc_vals = [s.server_proc_ms for s in ok_meas if s.server_proc_ms is not None]
    srv_svc_vals = [s.server_service_ms for s in ok_meas if s.server_service_ms is not None]

    # Chỉ tính thống kê phần dư ước lượng cho mẫu có residual_valid=True và giá trị >= 0
    valid_residuals = [
        s.network_residual_est_ms
        for s in ok_meas
        if s.residual_valid
        and s.network_residual_est_ms is not None
        and s.network_residual_est_ms >= 0.0
    ]
    residual_excluded = len(ok_meas) - len(valid_residuals)

    goodput = compute_directional_goodput(measurement_list, window_duration_s=window_duration_s)

    def _mean(vals: Sequence[float]) -> Optional[float]:
        return round(statistics.mean(vals), 4) if vals else None

    return ParsedCsvSummary(
        run_id=run_id,
        data_source=data_source,
        total_raw_rows=len(raw_list),
        warmup_rows_excluded=warmup_excluded,
        measurement_rows=len(measurement_list),
        ok_measurement_rows=len(ok_meas),
        residual_valid_rows=len(valid_residuals),
        residual_excluded_rows=residual_excluded,
        app_response_mean_ms=_mean(app_vals),
        app_response_p50_ms=percentile_nearest_rank(app_vals, 50),
        app_response_p95_ms=percentile_nearest_rank(app_vals, 95),
        server_proc_mean_ms=_mean(srv_proc_vals),
        server_service_mean_ms=_mean(srv_svc_vals),
        network_residual_est_mean_ms=_mean(valid_residuals),
        network_residual_est_p50_ms=percentile_nearest_rank(valid_residuals, 50),
        network_residual_est_p95_ms=percentile_nearest_rank(valid_residuals, 95),
        goodput=goodput,
        raw_rows=raw_list,
    )


def evaluate_load_sustained(
    samples: Sequence[ParsedSample],
    target_rate_rps_per_flow: float,
) -> Optional[bool]:
    """
    Kiểm tra quy tắc load_sustained theo docs/workload-spec.md §3.4:
      - Trên các request đo (is_warmup=0) của từng flow (n >= 2):
        1) actual_rate = (n - 1) / (t_send_last - t_send_first) >= 0.95 * target_rate
        2) P95(send_lag_ms) <= 0.5 * (1000 / target_rate)
      - Trả None nếu không đủ mẫu (n < 2).
    """
    meas = [s for s in samples if not s.is_warmup]
    if not meas or target_rate_rps_per_flow <= 0:
        return None

    by_flow: Dict[int, List[ParsedSample]] = {}
    for s in meas:
        fid = s.flow_id if s.flow_id is not None else 0
        by_flow.setdefault(fid, []).append(s)

    max_allowed_lag_ms = 0.5 * (1000.0 / target_rate_rps_per_flow)
    for flow_samples in by_flow.values():
        send_times = sorted(s.send_mono_ns for s in flow_samples if s.send_mono_ns is not None)
        if len(send_times) < 2:
            return None
        span_s = (send_times[-1] - send_times[0]) / 1e9
        if span_s <= 0:
            return False
        actual_rate = (len(send_times) - 1) / span_s
        if actual_rate < 0.95 * target_rate_rps_per_flow:
            return False

        lags = [s.send_lag_ms for s in flow_samples if s.send_lag_ms is not None]
        if lags:
            p95_lag = percentile_nearest_rank(lags, 95)
            if p95_lag is not None and p95_lag > max_allowed_lag_ms:
                return False
    return True


def validate_ab_pair(run_a: RunMetadata, run_b: RunMetadata) -> PairValidationResult:
    """
    Kiểm tra đầy đủ điều kiện ghép cặp đối chứng A/B (không chỉ dựa vào số flow):
      1. Cả hai lượt phải là dữ liệu thật (data_source == 'real').
      2. Đối chứng đúng 1 lượt Profile A và 1 lượt Profile B.
      3. Cùng config_id và cùng config_hash.
      4. Cùng điều kiện mạng (network_condition).
      5. Cả hai lượt đều đạt load_sustained == True.
      6. Đủ cửa sổ đo và có mẫu hợp lệ (sample_count > 0).
    """
    reasons: List[str] = []

    if run_a.data_source != "real" or run_b.data_source != "real":
        reasons.append("Không được dùng dữ liệu mô phỏng (simulated) để đối chứng nghiệm thu A/B.")

    if {run_a.profile.upper(), run_b.profile.upper()} != {"A", "B"}:
        reasons.append(
            f"Cặp đối chứng phải gồm 1 lượt Profile A và 1 lượt Profile B (nhận được: {run_a.profile}, {run_b.profile})."
        )

    if not run_a.config_id or run_a.config_id != run_b.config_id:
        reasons.append(f"Lệch config_id: '{run_a.config_id}' vs '{run_b.config_id}'.")

    if not run_a.config_hash or run_a.config_hash != run_b.config_hash:
        reasons.append(f"Lệch config_hash: '{run_a.config_hash}' vs '{run_b.config_hash}'.")

    if run_a.network_condition != run_b.network_condition:
        reasons.append("Điều kiện mạng (network_condition) giữa hai lượt không tương đương.")

    if run_a.load_sustained is not True:
        reasons.append(f"Lượt {run_a.run_id} chưa đạt điều kiện load_sustained=True.")
    if run_b.load_sustained is not True:
        reasons.append(f"Lượt {run_b.run_id} chưa đạt điều kiện load_sustained=True.")

    for meta in (run_a, run_b):
        if not meta.measurement_window_complete or meta.actual_window_s < meta.expected_window_s:
            reasons.append(
                f"Lượt {meta.run_id} chưa đủ cửa sổ đo ({meta.actual_window_s}s / {meta.expected_window_s}s)."
            )
        if meta.sample_count <= 0:
            reasons.append(f"Lượt {meta.run_id} không có mẫu đo hợp lệ.")

    return PairValidationResult(
        is_valid=len(reasons) == 0,
        reasons=reasons,
        run_a_id=run_a.run_id,
        run_b_id=run_b.run_id,
        sample_counts={run_a.run_id: run_a.sample_count, run_b.run_id: run_b.sample_count},
    )


def ensure_real_for_acceptance(summary: ParsedCsvSummary) -> None:
    """Chặn xuất kết quả từ chế độ mô phỏng thành kết quả nghiệm thu."""
    if summary.data_source != "real":
        raise SimulationExportError(
            f"Từ chối xuất kết quả nghiệm thu cho {summary.run_id}: nguồn dữ liệu là '{summary.data_source}'."
        )


def parse_csv_file(
    csv_path: pathlib.Path,
    data_source: str = "real",
    window_duration_s: Optional[float] = None,
    measurement_start_ns: Optional[int] = None,
) -> ParsedCsvSummary:
    samples, run_id = load_csv_samples(csv_path, measurement_start_ns=measurement_start_ns)
    return summarize_samples(
        samples,
        run_id=run_id,
        data_source=data_source,
        window_duration_s=window_duration_s,
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Nhóm 18 TV2 — Adapter đọc và kiểm định client-requests.csv theo schema hiện hành"
    )
    parser.add_argument("--csv", required=True, help="Đường dẫn tới file client-requests.csv")
    parser.add_argument(
        "--window-s",
        type=float,
        default=None,
        help="Thời lượng cửa sổ đo chính thức (giây) để tính goodput riêng từng chiều",
    )
    parser.add_argument(
        "--data-source",
        choices=["real", "simulated"],
        default="real",
        help="Đánh dấu nguồn dữ liệu (mặc định: real)",
    )
    args = parser.parse_args(argv)

    try:
        summary = parse_csv_file(
            pathlib.Path(args.csv),
            data_source=args.data_source,
            window_duration_s=args.window_s,
        )
        print(json.dumps(summary.to_report_dict(), indent=2, ensure_ascii=False))
        return 0
    except SchemaValidationError as exc:
        print(json.dumps({"error": "SchemaValidationError", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())