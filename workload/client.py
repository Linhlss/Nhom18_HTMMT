#!/usr/bin/python3
"""Open-loop request/response client for protocol tcp-binary-v1 (TV2, docs/workload-spec.md).

Runs the flows of the config that round-robin assigns to --client-name. Each flow has one TCP
connection; requests are sent on a fixed schedule t0 + k / rate, independent of responses
(open loop). A receiver thread matches responses by req_id and checks status, ID and byte size.

Exit codes: 0 all expected responses valid; 2 config/usage error; 3 connection error;
4 validation error (wrong/unknown ID, wrong size, server status, framing); 5 timeout only.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import socket
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.evidence import utc_iso  # noqa: E402
from tools.stats import describe, percentile_nearest_rank  # noqa: E402
from workload import framing  # noqa: E402
from workload.config import ConfigError, flow_plan, load, offered_load_mbps  # noqa: E402
from workload.protocol import STATUS_OK, req_id, request_meta  # noqa: E402

CSV_COLUMNS = [
    'run_id', 'config_id', 'profile', 'run_kind', 'is_warmup', 'flow_id', 'client_host', 'server_host',
    'server_ip', 'server_port', 'src_port', 'req_id', 'seq', 'scheduled_send_mono_ns', 'send_mono_ns',
    'recv_mono_ns', 'send_utc', 'recv_utc', 'send_lag_ms', 'req_bytes_sent', 'resp_bytes_expected',
    'resp_bytes_received', 'app_response_ms', 'server_queue_ms', 'server_service_ms', 'server_proc_ms',
    'network_residual_est_ms', 'residual_valid', 'status', 'error']
LOAD_RATE_RATIO_MIN = 0.95      # achieved send rate >= 95 % of target
LOAD_LAG_P95_MAX_INTERVALS = 0.5  # p95 send lag <= half an inter-request interval
EXIT_OK, EXIT_CONFIG, EXIT_CONN, EXIT_INVALID, EXIT_TIMEOUT = 0, 2, 3, 4, 5


class Flow:
    def __init__(self, cfg, plan, args, t0_holder):
        self.cfg, self.plan, self.args = cfg, plan, args
        self.flow_id = plan['flow_id']
        self.server = plan['server']
        self.rows = {}           # req_id -> row dict
        self.unmatched = []      # responses whose req_id was not pending
        self.errors = []
        self.sock = None
        self.src_port = ''
        self.conn_error = None
        self.lock = threading.Lock()
        self.t0_holder = t0_holder

    def connect(self, deadline):
        last = None
        while time.monotonic() < deadline:
            try:
                self.sock = socket.create_connection((self.server['ip'], self.server['port']), timeout=2)
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.src_port = self.sock.getsockname()[1]
                return True
            except OSError as error:
                last = error
                time.sleep(0.2)
        self.conn_error = f'connect {self.server["ip"]}:{self.server["port"]} failed: {last}'
        return False

    def n_requests(self):
        e, w = self.cfg['execution'], self.cfg['workload']
        horizon = e['warmup_sec'] + e['duration_sec']
        n = math.floor(horizon * w['rate_rps_per_flow'] - 1e-9) + 1  # sends at k/rate < horizon
        return min(n, e['max_requests_per_flow']) if e['max_requests_per_flow'] else n

    def new_row(self, seq, scheduled_ns):
        w = self.cfg['workload']
        t0 = self.t0_holder[0]
        return {'run_id': self.args.run_id, 'config_id': self.cfg['config_id'], 'profile': self.args.profile,
                'run_kind': self.cfg['run_kind'],
                'is_warmup': int((scheduled_ns - t0) / 1e9 < self.cfg['execution']['warmup_sec']),
                'flow_id': self.flow_id, 'client_host': self.args.client_name,
                'server_host': self.server['name'], 'server_ip': self.server['ip'],
                'server_port': self.server['port'], 'src_port': self.src_port,
                'req_id': req_id(self.args.run_id, self.flow_id, seq), 'seq': seq,
                'scheduled_send_mono_ns': scheduled_ns, 'send_mono_ns': '', 'recv_mono_ns': '',
                'send_utc': '', 'recv_utc': '', 'send_lag_ms': '', 'req_bytes_sent': '',
                'resp_bytes_expected': w['resp_size_bytes'], 'resp_bytes_received': '',
                'app_response_ms': '', 'server_queue_ms': '', 'server_service_ms': '', 'server_proc_ms': '',
                'network_residual_est_ms': '', 'residual_valid': '', 'status': 'PENDING', 'error': ''}

    def run(self):
        """Called after connect() and the shared start barrier."""
        w, e = self.cfg['workload'], self.cfg['execution']
        n = self.n_requests()
        interval_ns = 1e9 / w['rate_rps_per_flow']
        t0 = self.t0_holder[0]
        for seq in range(n):
            self.rows[req_id(self.args.run_id, self.flow_id, seq)] = self.new_row(seq, int(t0 + seq * interval_ns))
        if self.sock is None:
            for row in self.rows.values():
                row['status'], row['error'] = 'CONN_ERROR', self.conn_error
            return
        last_sched = t0 + (n - 1) * interval_ns
        deadline_ns = last_sched + e['timeout_ms'] * 1e6 + 1e9
        receiver = threading.Thread(target=self.receive, args=(deadline_ns,), daemon=True)
        receiver.start()
        for seq in range(n):
            rid = req_id(self.args.run_id, self.flow_id, seq)
            row = self.rows[rid]
            delay = (row['scheduled_send_mono_ns'] - time.monotonic_ns()) / 1e9
            if delay > 0:
                time.sleep(delay)
            send_utc = utc_iso()
            meta = request_meta(self.args.run_id, self.cfg['config_id'], self.flow_id, seq,
                                self.args.client_name, send_utc, w['resp_size_bytes'], w['service_delay_ms'])
            frame = framing.encode(meta, w['req_size_bytes'])
            with self.lock:
                row['send_mono_ns'] = time.monotonic_ns()
                row['send_utc'] = send_utc
                row['send_lag_ms'] = round((row['send_mono_ns'] - row['scheduled_send_mono_ns']) / 1e6, 6)
                row['status'] = 'SENT'
            try:
                self.sock.sendall(frame)
                row['req_bytes_sent'] = len(frame)
            except OSError as error:
                with self.lock:
                    row['status'], row['error'] = 'SEND_ERROR', str(error)
                break
        receiver.join(timeout=max(0.0, (deadline_ns - time.monotonic_ns()) / 1e9) + 2)
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()
        with self.lock:
            for row in self.rows.values():
                if row['status'] in ('PENDING', 'SENT'):
                    row['status'] = 'TIMEOUT' if row['status'] == 'SENT' else 'NOT_SENT'

    def pending(self):
        with self.lock:
            return sum(1 for r in self.rows.values() if r['status'] in ('PENDING', 'SENT'))

    def receive(self, deadline_ns):
        timeout_ms = self.cfg['execution']['timeout_ms']
        while self.pending():
            remaining = (deadline_ns - time.monotonic_ns()) / 1e9
            if remaining <= 0:
                return
            self.sock.settimeout(remaining)
            try:
                meta, nbytes = framing.read_frame(self.sock)
            except socket.timeout:
                return
            except (EOFError, ConnectionError, OSError, framing.FrameError) as error:
                self.errors.append(f'receive: {error}')
                with self.lock:
                    for r in self.rows.values():
                        if r['status'] == 'SENT':
                            r['status'], r['error'] = 'PROTOCOL_ERROR', str(error)
                return
            recv_ns, recv_utc = time.monotonic_ns(), utc_iso()
            with self.lock:
                row = self.rows.get(meta.get('req_id'))
                if row is None or row['status'] != 'SENT':
                    self.unmatched.append({'req_id': meta.get('req_id'), 'bytes': nbytes, 'recv_utc': recv_utc,
                                           'status': meta.get('status')})
                    continue
                row.update(recv_mono_ns=recv_ns, recv_utc=recv_utc, resp_bytes_received=nbytes)
                app_ms = (recv_ns - row['send_mono_ns']) / 1e6
                row['app_response_ms'] = round(app_ms, 6)
                for key in ('server_queue_ms', 'server_service_ms', 'server_proc_ms'):
                    if isinstance(meta.get(key), (int, float)):
                        row[key] = meta[key]
                problems = []
                if meta.get('run_id') != self.args.run_id or meta.get('flow_id') != self.flow_id \
                        or meta.get('seq') != row['seq']:
                    problems.append('run_id/flow_id/seq mismatch')
                if nbytes != row['resp_bytes_expected']:
                    problems.append(f'size {nbytes} != expected {row["resp_bytes_expected"]}')
                if meta.get('status') != STATUS_OK:
                    problems.append(f'server status {meta.get("status")}')
                if row['server_proc_ms'] == '':
                    problems.append('server_proc_ms missing')
                else:
                    residual = app_ms - row['server_proc_ms']
                    row['network_residual_est_ms'] = round(residual, 6)
                    row['residual_valid'] = int(residual >= 0)
                if problems:
                    row['status'] = 'SIZE_MISMATCH' if any(p.startswith('size') for p in problems) else 'INVALID_RESPONSE'
                    row['error'] = '; '.join(problems)
                elif app_ms > timeout_ms:
                    row['status'], row['error'] = 'TIMEOUT', f'response after {app_ms:.3f} ms > timeout'
                else:
                    row['status'] = 'OK'


def load_check(flows, rate):
    """Target vs achieved send rate per flow over measured (non-warm-up) sends."""
    per_flow, sustained = [], True
    interval_ms = 1000 / rate
    for f in flows:
        sent = sorted((r for r in f.rows.values() if r['send_mono_ns'] != '' and r['is_warmup'] == 0),
                      key=lambda r: r['seq'])
        if len(sent) < 2:
            per_flow.append({'flow_id': f.flow_id, 'measured_sends': len(sent), 'rate_achieved_send_rps': None,
                             'send_lag_p95_ms': None, 'load_sustained': None})
            sustained = None if sustained is not False else False
            continue
        span = (sent[-1]['send_mono_ns'] - sent[0]['send_mono_ns']) / 1e9
        achieved = (len(sent) - 1) / span if span > 0 else None
        lag95 = percentile_nearest_rank([r['send_lag_ms'] for r in sent], 95)
        ok = achieved is not None and achieved >= LOAD_RATE_RATIO_MIN * rate \
            and lag95 <= LOAD_LAG_P95_MAX_INTERVALS * interval_ms
        per_flow.append({'flow_id': f.flow_id, 'measured_sends': len(sent),
                         'rate_achieved_send_rps': achieved, 'send_lag_p95_ms': lag95, 'load_sustained': ok})
        if sustained is not None:
            sustained = sustained and ok
    return per_flow, sustained


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--config', required=True)
    p.add_argument('--client-name', required=True, choices=['c1', 'c2'])
    p.add_argument('--run-id', required=True)
    p.add_argument('--profile', required=True, choices=['A', 'B', 'unknown'],
                   help='network profile reported by networkctl status (kept separate from config_id)')
    p.add_argument('--out', required=True)
    p.add_argument('--connect-retry-sec', type=float, default=5.0)
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started_utc = utc_iso()
    try:
        cfg = load(args.config)
    except (OSError, ConfigError) as error:
        summary = {'run_id': args.run_id, 'exit_code': EXIT_CONFIG,
                   'errors': getattr(error, 'problems', [str(error)])}
        (out / 'client-summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
        print(json.dumps(summary, ensure_ascii=False))
        return EXIT_CONFIG
    plans = [f for f in flow_plan(cfg) if f['client']['name'] == args.client_name]
    if not plans:
        print(json.dumps({'error': f'no flows assigned to {args.client_name}'}))
        return EXIT_CONFIG
    t0_holder = [0]
    flows = [Flow(cfg, plan, args, t0_holder) for plan in plans]
    deadline = time.monotonic() + args.connect_retry_sec
    connectors = [threading.Thread(target=f.connect, args=(deadline,)) for f in flows]
    for t in connectors:
        t.start()
    for t in connectors:
        t.join()
    t0_holder[0] = time.monotonic_ns() + 50_000_000  # common start 50 ms after all connects
    t0_utc = utc_iso()
    runners = [threading.Thread(target=f.run) for f in flows]
    for t in runners:
        t.start()
    for t in runners:
        t.join()

    rows = sorted((r for f in flows for r in f.rows.values()), key=lambda r: (r['flow_id'], r['seq']))
    with (out / 'client-requests.csv').open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    statuses = {}
    for r in rows:
        statuses[r['status']] = statuses.get(r['status'], 0) + 1
    unmatched = [u for f in flows for u in f.unmatched]
    conn_errors = [f.conn_error for f in flows if f.conn_error]
    invalid = sum(v for k, v in statuses.items() if k in ('SIZE_MISMATCH', 'INVALID_RESPONSE', 'PROTOCOL_ERROR'))
    timeouts = sum(v for k, v in statuses.items() if k in ('TIMEOUT', 'NOT_SENT', 'SEND_ERROR'))
    if conn_errors:
        code = EXIT_CONN
    elif invalid or unmatched:
        code = EXIT_INVALID
    elif timeouts:
        code = EXIT_TIMEOUT
    else:
        code = EXIT_OK if statuses.get('OK', 0) == len(rows) and rows else EXIT_TIMEOUT
    per_flow, sustained = load_check(flows, cfg['workload']['rate_rps_per_flow'])
    measured_ok = [r for r in rows if r['status'] == 'OK' and r['is_warmup'] == 0]
    summary = {
        'run_id': args.run_id, 'config_id': cfg['config_id'], 'config_sha256': cfg['_config_sha256'],
        'config_path': args.config, 'profile': args.profile, 'run_kind': cfg['run_kind'],
        'client_host': args.client_name, 'started_utc': started_utc, 't0_utc': t0_utc, 'finished_utc': utc_iso(),
        'flows': [{'flow_id': f.flow_id, 'server': f.server, 'src_port': f.src_port,
                   'conn_error': f.conn_error, 'errors': f.errors} for f in flows],
        'requests_expected': len(rows), 'status_counts': statuses, 'unmatched_responses': unmatched,
        'all_ok': code == EXIT_OK,
        'target_offered_load_app': offered_load_mbps(cfg),
        'rate_target_rps_per_flow': cfg['workload']['rate_rps_per_flow'],
        'load_check': {'rule': f'achieved >= {LOAD_RATE_RATIO_MIN} x target and p95 send lag <= '
                               f'{LOAD_LAG_P95_MAX_INTERVALS} x interval; None = too few samples',
                       'per_flow': per_flow, 'load_sustained': sustained},
        'app_response_ms': describe([r['app_response_ms'] for r in measured_ok]),
        'server_proc_ms': describe([r['server_proc_ms'] for r in measured_ok]),
        'network_residual_est_ms_valid': describe([r['network_residual_est_ms'] for r in measured_ok
                                                   if r['residual_valid'] == 1]),
        'residual_invalid_count': sum(1 for r in measured_ok if r['residual_valid'] == 0),
        'percentile_method': 'nearest-rank over measured OK requests (is_warmup=0)',
        'exit_code': code,
    }
    (out / 'client-summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({k: summary[k] for k in ('run_id', 'requests_expected', 'status_counts', 'exit_code')}))
    return code


if __name__ == '__main__':
    sys.exit(main())
