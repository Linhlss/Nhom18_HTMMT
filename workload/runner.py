#!/usr/bin/env python3
"""
Nhóm 18 — Hệ thống và Mạng máy tính (MI4060)
Module: workload/runner.py (Task N18-010)
Vai trò: TV2 (Workload / UI Lead)

Điều phối 1/2/4/8 concurrent flows phân bổ luân phiên giữa 2 client logic c1 (10.18.1.10)
và c2 (10.18.2.10) tới server a1 (10.18.3.11:8000) và a2 (10.18.3.12:8000).
Hỗ trợ 2 chế độ:
  - --mode mininet: Chạy qua sudo /usr/bin/python3 control/networkctl.py exec trên Ubuntu VM.
  - --mode local:   Chạy trực tiếp trên localhost (127.0.0.1) để unit test / kiểm thử nhanh.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
import pathlib
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

CURRENT_DIR = pathlib.Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import client as wl_client  # noqa: E402

VALID_CONCURRENCY = (1, 2, 4, 8)

DEFAULT_CLIENT_HOSTS = ("c1", "c2")
DEFAULT_SERVER_HOSTS = ("a1", "a2")
SERVER_IP_MAP = {
    "a1": "10.18.3.11",
    "a2": "10.18.3.12",
}


def build_flow_plan(
    concurrency: int,
    local_mode: bool = False,
    local_ports: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Lập kế hoạch phân bổ luồng luân phiên giữa c1 và c2:
      - flow_id chẵn (0, 2, 4, 6) -> c1
      - flow_id lẻ   (1, 3, 5, 7) -> c2
    Đồng thời phân bổ luân phiên đích server a1 / a2 để cân bằng tải hai server.
    """
    if concurrency not in VALID_CONCURRENCY:
        raise ValueError(
            f"concurrency={concurrency} không hợp lệ; chỉ hỗ trợ {VALID_CONCURRENCY}"
        )

    plan: List[Dict[str, Any]] = []
    for flow_id in range(concurrency):
        client_host = DEFAULT_CLIENT_HOSTS[flow_id % 2]
        server_host = DEFAULT_SERVER_HOSTS[flow_id % 2]
        if local_mode:
            target_ip = "127.0.0.1"
            port = local_ports[flow_id % len(local_ports)] if local_ports else 8000
        else:
            target_ip = SERVER_IP_MAP[server_host]
            port = 8000

        plan.append(
            {
                "flow_id": flow_id,
                "client_host": client_host,
                "server_host": server_host,
                "target_ip": target_ip,
                "port": port,
            }
        )
    return plan


def run_single_flow_task(flow_cfg: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    """Chạy 1 flow TCP thông qua workload/client.py và trả về thống kê cấp flow."""
    cli_argv = [
        "--target",
        str(flow_cfg["target_ip"]),
        "--port",
        str(flow_cfg["port"]),
        "--client-host",
        str(flow_cfg["client_host"]),
        "--run-id",
        args.run_id,
        "--config-id",
        args.config_id,
        "--profile",
        args.profile,
        "--flow-id",
        str(flow_cfg["flow_id"]),
        "--req-size-bytes",
        str(args.req_size_bytes),
        "--resp-size-bytes",
        str(args.resp_size_bytes),
        "--service-delay-ms",
        str(args.service_delay_ms),
        "--rate-rps",
        str(args.rate_rps),
        "--count",
        str(args.count),
        "--warmup-sec",
        str(args.warmup_sec),
        "--duration-sec",
        str(args.duration_sec),
        "--timeout-ms",
        str(args.timeout_ms),
    ]
    cli_args = wl_client.parse_args(cli_argv)
    t0 = time.perf_counter()
    records, exit_code = wl_client.execute_flow(cli_args)
    duration_sec = time.perf_counter() - t0

    ok_count = sum(1 for r in records if r["status"] == "OK")
    err_count = len(records) - ok_count
    valid_rtts = [r["net_rtt_est_ms"] for r in records if r["status"] == "OK" and r["is_warmup"] == 0]
    avg_net_rtt = (sum(valid_rtts) / len(valid_rtts)) if valid_rtts else 0.0

    return {
        "flow_id": flow_cfg["flow_id"],
        "client_host": flow_cfg["client_host"],
        "server_host": flow_cfg["server_host"],
        "requests": len(records),
        "ok_requests": ok_count,
        "error_requests": err_count,
        "duration_sec": round(duration_sec, 4),
        "avg_net_rtt_est_ms": round(avg_net_rtt, 3),
        "status": "OK" if (exit_code == 0 and err_count == 0 and len(records) > 0) else "FAILED",
        "records": records,
    }


def run_worker_mode(args: argparse.Namespace) -> int:
    """
    Chế độ worker chạy bên trong 1 host/namespace (c1 hoặc c2):
    mở song song các flow được giao cho host đó bằng ThreadPoolExecutor.
    """
    flow_specs = json.loads(args.worker_flows_json)
    flow_results: List[Dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(flow_specs)) as pool:
        futures = [pool.submit(run_single_flow_task, spec, args) for spec in flow_specs]
        for fut in concurrent.futures.as_completed(futures):
            flow_results.append(fut.result())

    flow_results.sort(key=lambda x: x["flow_id"])
    payload = {
        "client_host": args.client_host,
        "flow_results": flow_results,
    }
    print("WORKER_RESULT_JSON:" + json.dumps(payload, ensure_ascii=False), flush=True)
    all_ok = all(f["status"] == "OK" for f in flow_results)
    return 0 if all_ok else 1


def extract_worker_payload(stdout_text: str) -> Dict[str, Any]:
    """Trích xuất dòng WORKER_RESULT_JSON từ stdout của tiến trình worker."""
    for line in reversed(stdout_text.splitlines()):
        if line.startswith("WORKER_RESULT_JSON:"):
            return json.loads(line[len("WORKER_RESULT_JSON:") :])
    raise ValueError(f"Không tìm thấy WORKER_RESULT_JSON trong output: {stdout_text[-500:]}")


def run_networkctl_exec(
    networkctl_path: str,
    host: str,
    timeout_sec: float,
    cmd_argv: List[str],
) -> subprocess.CompletedProcess[str]:
    """Gọi control/networkctl.py exec theo đúng chuẩn bàn giao của TV1."""
    full_cmd = [
        "/usr/bin/python3",
        networkctl_path,
        "exec",
        "--timeout",
        str(min(600, max(10, int(timeout_sec)))),
        host,
        "--",
        *cmd_argv,
    ]
    if os.geteuid() != 0:
        full_cmd = ["sudo", *full_cmd]

    return subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout_sec + 15)


def orchestrate_mininet(plan: List[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    """
    Chạy đồng thời server trên a1/a2 (nếu --manage-servers) và 2 client logic c1/c2
    qua control/networkctl.py exec.
    """
    repo_root = pathlib.Path(args.repo_root).resolve()
    networkctl_path = str(repo_root / "control" / "networkctl.py")
    runner_rel_path = str(pathlib.Path(__file__).resolve())
    server_rel_path = str((CURRENT_DIR / "server.py").resolve())

    # Tính thời gian an toàn cho server và exec
    work_sec = args.warmup_sec + args.duration_sec if args.duration_sec > 0 else max(15.0, args.count / max(args.rate_rps, 0.5) + 5.0)
    srv_duration = work_sec + 8.0
    exec_timeout = min(600.0, srv_duration + 15.0)

    by_client: Dict[str, List[Dict[str, Any]]] = {}
    for item in plan:
        by_client.setdefault(item["client_host"], []).append(item)

    server_futures: List[concurrent.futures.Future[subprocess.CompletedProcess[str]]] = []
    client_futures: Dict[str, concurrent.futures.Future[subprocess.CompletedProcess[str]]] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        if args.manage_servers:
            used_servers = sorted({item["server_host"] for item in plan})
            for srv in used_servers:
                srv_cmd = [
                    "/usr/bin/python3",
                    server_rel_path,
                    "--bind",
                    SERVER_IP_MAP[srv],
                    "--port",
                    "8000",
                    "--server-host",
                    srv,
                    "--duration",
                    str(srv_duration),
                    "--service-delay-ms",
                    str(args.service_delay_ms),
                    "--resp-size-bytes",
                    str(args.resp_size_bytes),
                ]
                server_futures.append(
                    pool.submit(run_networkctl_exec, networkctl_path, srv, exec_timeout, srv_cmd)
                )
            time.sleep(1.0)  # Đợi server bind cổng 8000 xong

        for chost, flows in sorted(by_client.items()):
            worker_cmd = [
                "/usr/bin/python3",
                runner_rel_path,
                "--worker",
                "--client-host",
                chost,
                "--run-id",
                args.run_id,
                "--config-id",
                args.config_id,
                "--profile",
                args.profile,
                "--req-size-bytes",
                str(args.req_size_bytes),
                "--resp-size-bytes",
                str(args.resp_size_bytes),
                "--service-delay-ms",
                str(args.service_delay_ms),
                "--rate-rps",
                str(args.rate_rps),
                "--count",
                str(args.count),
                "--warmup-sec",
                str(args.warmup_sec),
                "--duration-sec",
                str(args.duration_sec),
                "--timeout-ms",
                str(args.timeout_ms),
                "--worker-flows-json",
                json.dumps(flows, separators=(",", ":")),
            ]
            client_futures[chost] = pool.submit(
                run_networkctl_exec, networkctl_path, chost, exec_timeout, worker_cmd
            )

        all_flow_results: List[Dict[str, Any]] = []
        for chost, fut in client_futures.items():
            proc = fut.result()
            if proc.returncode != 0 and "WORKER_RESULT_JSON:" not in proc.stdout:
                raise RuntimeError(
                    f"Worker trên {chost} thất bại (rc={proc.returncode}): {proc.stderr or proc.stdout}"
                )
            payload = extract_worker_payload(proc.stdout)
            all_flow_results.extend(payload["flow_results"])

        for sfut in server_futures:
            sfut.result()

    all_flow_results.sort(key=lambda x: x["flow_id"])
    return all_flow_results


def orchestrate_local(plan: List[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    """Chạy song song các flow trên localhost để phục vụ kiểm thử đơn vị và xác minh logic."""
    by_client: Dict[str, List[Dict[str, Any]]] = {}
    for item in plan:
        by_client.setdefault(item["client_host"], []).append(item)

    def run_client_group(chost: str, flows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        worker_args = argparse.Namespace(**vars(args))
        worker_args.client_host = chost
        group_results: List[Dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(flows)) as inner_pool:
            futs = [inner_pool.submit(run_single_flow_task, spec, worker_args) for spec in flows]
            for f in concurrent.futures.as_completed(futs):
                group_results.append(f.result())
        return group_results

    all_flow_results: List[Dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(by_client)) as outer_pool:
        futs = [
            outer_pool.submit(run_client_group, chost, flows)
            for chost, flows in sorted(by_client.items())
        ]
        for f in concurrent.futures.as_completed(futs):
            all_flow_results.extend(f.result())

    all_flow_results.sort(key=lambda x: x["flow_id"])
    return all_flow_results


def save_outputs(
    flow_results: List[Dict[str, Any]],
    total_duration_sec: float,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """Tổng hợp số request, status, duration và lưu CSV + JSON summary."""
    all_records: List[Dict[str, Any]] = []
    flow_summaries: List[Dict[str, Any]] = []

    for fr in flow_results:
        all_records.extend(fr["records"])
        flow_summaries.append(
            {
                "flow_id": fr["flow_id"],
                "client_host": fr["client_host"],
                "server_host": fr["server_host"],
                "requests": fr["requests"],
                "ok_requests": fr["ok_requests"],
                "error_requests": fr["error_requests"],
                "duration_sec": fr["duration_sec"],
                "avg_net_rtt_est_ms": fr["avg_net_rtt_est_ms"],
                "status": fr["status"],
            }
        )

    all_records.sort(key=lambda r: (r["send_ts_ns"], r["flow_id"]))

    if args.csv_out:
        csv_path = pathlib.Path(args.csv_out)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=wl_client.CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(all_records)

    total_reqs = sum(fr["requests"] for fr in flow_results)
    ok_reqs = sum(fr["ok_requests"] for fr in flow_results)
    err_reqs = sum(fr["error_requests"] for fr in flow_results)
    overall_status = "OK" if (len(flow_results) == args.concurrency and err_reqs == 0 and total_reqs > 0) else "FAILED"

    summary = {
        "run_id": args.run_id,
        "config_id": args.config_id,
        "profile": args.profile,
        "concurrency": args.concurrency,
        "total_requests": total_reqs,
        "ok_requests": ok_reqs,
        "error_requests": err_reqs,
        "duration_sec": round(total_duration_sec, 4),
        "status": overall_status,
        "flows": flow_summaries,
    }

    if args.summary_out:
        sum_path = pathlib.Path(args.summary_out)
        sum_path.parent.mkdir(parents=True, exist_ok=True)
        sum_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    return summary


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nhóm 18 TV2 — Runner điều phối 1/2/4/8 concurrent flows giữa c1 và c2"
    )
    parser.add_argument("--mode", choices=["mininet", "local"], default="mininet")
    parser.add_argument("--concurrency", type=int, default=4, choices=VALID_CONCURRENCY)
    parser.add_argument("--profile", choices=["A", "B"], default="A")
    parser.add_argument("--run-id", default="w3_concurrency_run")
    parser.add_argument("--config-id", default="cfg_w3_concurrency")
    parser.add_argument("--req-size-bytes", type=int, default=1024)
    parser.add_argument("--resp-size-bytes", type=int, default=65536)
    parser.add_argument("--service-delay-ms", type=float, default=5.0)
    parser.add_argument("--rate-rps", type=float, default=10.0)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--warmup-sec", type=float, default=0.0)
    parser.add_argument("--duration-sec", type=float, default=0.0)
    parser.add_argument("--timeout-ms", type=float, default=5000.0)
    parser.add_argument("--local-ports", default="8000", help="Danh sách cổng cách nhau bởi dấu phẩy khi chạy --mode local")
    parser.add_argument("--manage-servers", action="store_true", help="Tự động bật/tắt server.py trên a1/a2 qua networkctl.py exec")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--csv-out", default=None)
    parser.add_argument("--summary-out", default=None)

    # Tham số nội bộ cho worker chạy trong namespace c1/c2
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--client-host", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--worker-flows-json", default="[]", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.worker:
        return run_worker_mode(args)

    is_local = args.mode == "local"
    local_ports = [int(p.strip()) for p in args.local_ports.split(",") if p.strip()]
    plan = build_flow_plan(args.concurrency, local_mode=is_local, local_ports=local_ports)

    t0 = time.perf_counter()
    if is_local:
        flow_results = orchestrate_local(plan, args)
    else:
        flow_results = orchestrate_mininet(plan, args)
    total_duration = time.perf_counter() - t0

    summary = save_outputs(flow_results, total_duration, args)
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    return 0 if summary["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())