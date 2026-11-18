#!/usr/bin/env python3
"""Load and validate a workload config (docs/workload-spec.md §3). Standard library only.

Usage: python3 workload/config.py workload/configs/<file>.json   -> exit 0 if valid, 2 if not.
"""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workload.framing import MAX_FRAME_BYTES  # noqa: E402
from workload.protocol import MAX_SERVICE_DELAY_MS, PROTOCOL, min_request_bytes, min_response_bytes  # noqa: E402

try:  # Cross-check names/IPs with TV1's topology when available (stdlib-only module).
    from topology.model import IPS as TOPOLOGY_IPS  # noqa: E402
except Exception:  # pragma: no cover - topology is part of the repo
    TOPOLOGY_IPS = {}

ID_RE = re.compile(r'^[a-z0-9][a-z0-9_.-]{0,63}$')
APP_PORT = 8000
EXEC_LIMIT_SEC = 600
BENCHMARK_CONCURRENCY = (1, 2, 4, 8)


class ConfigError(ValueError):
    def __init__(self, problems):
        super().__init__('; '.join(problems))
        self.problems = problems


def _num(value, integer=False):
    if isinstance(value, bool):
        return False
    return isinstance(value, int) if integer else isinstance(value, (int, float))


def validate(cfg):
    """Return a list of problems; empty list means valid."""
    p = []
    if not isinstance(cfg, dict):
        return ['config must be a JSON object']
    if cfg.get('schema_version') != 1:
        p.append('schema_version must be 1')
    if not isinstance(cfg.get('config_id'), str) or not ID_RE.match(cfg['config_id']):
        p.append('config_id must match ^[a-z0-9][a-z0-9_.-]{0,63}$')
    run_kind = cfg.get('run_kind')
    if run_kind not in ('smoke', 'benchmark'):
        p.append('run_kind must be "smoke" or "benchmark"')
    if cfg.get('protocol') != PROTOCOL:
        p.append(f'protocol must be "{PROTOCOL}" (HTTP is a future extension, not specified in v1)')

    net = cfg.get('network') if isinstance(cfg.get('network'), dict) else {}
    if not net:
        p.append('network object missing')
    for role, keys in (('clients', ('name', 'ip')), ('servers', ('name', 'ip', 'port'))):
        items = net.get(role)
        if not isinstance(items, list) or not items:
            p.append(f'network.{role} must be a non-empty list of objects {{{"/".join(keys)}}}')
            continue
        names = set()
        for i, item in enumerate(items):
            where = f'network.{role}[{i}]'
            if not isinstance(item, dict) or set(item) != set(keys):
                p.append(f'{where} must have exactly the keys {list(keys)}')
                continue
            if not isinstance(item['name'], str) or item['name'] in names:
                p.append(f'{where}.name must be a unique string')
            names.add(item['name'])
            try:
                ipaddress.IPv4Address(item['ip'])
            except (ipaddress.AddressValueError, TypeError):
                p.append(f'{where}.ip is not an IPv4 address')
            loopback_test = os.environ.get('NHOM18_ALLOW_LOOPBACK') == '1' and item['ip'] == '127.0.0.1'
            if TOPOLOGY_IPS and TOPOLOGY_IPS.get(item['name']) != item['ip'] and not loopback_test:
                p.append(f'{where}: {item["name"]}={item["ip"]} does not match topology '
                         f'({TOPOLOGY_IPS.get(item["name"], "unknown host")})')
            if role == 'clients' and item['name'] not in ('c1', 'c2'):
                p.append(f'{where}.name must be c1 or c2')
            if role == 'servers':
                if item['name'] not in ('a1', 'a2'):
                    p.append(f'{where}.name must be a1 or a2')
                if item['port'] != APP_PORT or not _num(item['port'], True):
                    p.append(f'{where}.port must be {APP_PORT} (firewall allows TCP/{APP_PORT} for the app)')
    if net.get('client_assignment') != 'round_robin':
        p.append('network.client_assignment must be "round_robin"')

    w = cfg.get('workload') if isinstance(cfg.get('workload'), dict) else {}
    if not w:
        p.append('workload object missing')
    req_min, resp_min = min_request_bytes(), min_response_bytes()
    for key, low in (('req_size_bytes', req_min), ('resp_size_bytes', resp_min)):
        v = w.get(key)
        if not _num(v, True) or not low <= v <= MAX_FRAME_BYTES:
            p.append(f'workload.{key} must be an integer in [{low}, {MAX_FRAME_BYTES}] '
                     f'(includes 8 B header + JSON metadata + padding)')
    rate = w.get('rate_rps_per_flow')
    if not _num(rate) or not 0 < rate <= 1000:
        p.append('workload.rate_rps_per_flow must be in (0, 1000] requests/s per flow')
    conc = w.get('concurrency')
    if not _num(conc, True) or not 1 <= conc <= 8:
        p.append('workload.concurrency must be an integer 1..8')
    elif run_kind == 'benchmark' and conc not in BENCHMARK_CONCURRENCY:
        p.append('benchmark concurrency must be one of 1, 2, 4, 8')
    delay = w.get('service_delay_ms')
    if not _num(delay) or not 0 <= delay <= MAX_SERVICE_DELAY_MS:
        p.append(f'workload.service_delay_ms must be in [0, {MAX_SERVICE_DELAY_MS:g}]')

    e = cfg.get('execution') if isinstance(cfg.get('execution'), dict) else {}
    if not e:
        p.append('execution object missing')
    warm, dur, tmo = e.get('warmup_sec'), e.get('duration_sec'), e.get('timeout_ms')
    maxreq, seed = e.get('max_requests_per_flow', None), e.get('seed')
    if not _num(warm) or warm < 0:
        p.append('execution.warmup_sec must be >= 0')
    if not _num(dur) or dur <= 0:
        p.append('execution.duration_sec must be > 0')
    if not _num(tmo, True) or not 1 <= tmo <= 60_000:
        p.append('execution.timeout_ms must be an integer in [1, 60000]')
    if maxreq is not None and (not _num(maxreq, True) or maxreq < 1):
        p.append('execution.max_requests_per_flow must be null or an integer >= 1')
    if not _num(seed, True) or seed < 0:
        p.append('execution.seed must be an integer >= 0')
    if run_kind == 'benchmark':
        if _num(warm) and warm < 2:
            p.append('benchmark requires warmup_sec >= 2')
        if _num(dur) and dur < 10:
            p.append('benchmark requires duration_sec >= 10')
        if maxreq is not None:
            p.append('benchmark must be duration-based: max_requests_per_flow must be null')
    if run_kind == 'smoke' and maxreq is None:
        p.append('smoke run requires max_requests_per_flow')
    if all(_num(x) for x in (warm, dur, tmo)) and warm + dur + tmo / 1000 + 15 > EXEC_LIMIT_SEC:
        p.append(f'warmup + duration + timeout + 15 s margin must stay below exec limit {EXEC_LIMIT_SEC} s')
    if _num(rate) and _num(warm) and _num(dur) and maxreq is not None and _num(maxreq, True) \
            and (maxreq - 1) / rate > warm + dur:
        p.append('max_requests_per_flow cannot be scheduled within warmup_sec + duration_sec at this rate')
    return p


def load(path):
    raw = Path(path).read_bytes()
    try:
        cfg = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConfigError([f'not valid UTF-8 JSON: {error}']) from error
    problems = validate(cfg)
    if problems:
        raise ConfigError(problems)
    cfg['_config_sha256'] = hashlib.sha256(raw).hexdigest()
    return cfg


def flow_plan(cfg):
    """Deterministic round-robin: flow i -> clients[i % nc], servers[i % ns]."""
    clients, servers = cfg['network']['clients'], cfg['network']['servers']
    return [{'flow_id': i, 'client': clients[i % len(clients)], 'server': servers[i % len(servers)]}
            for i in range(cfg['workload']['concurrency'])]


def offered_load_mbps(cfg):
    """Target application-layer offered load per direction (links are full duplex), spec §3.3.

    Excludes TCP/IP/Ethernet headers, so on-wire load is somewhat higher."""
    w = cfg['workload']
    k = w['concurrency'] * w['rate_rps_per_flow'] * 8 / 1e6
    return {'client_to_server_mbps': round(k * w['req_size_bytes'], 6),
            'server_to_client_mbps': round(k * w['resp_size_bytes'], 6)}


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        cfg = load(argv[1])
    except (OSError, ConfigError) as error:
        print(json.dumps({'valid': False, 'problems': getattr(error, 'problems', [str(error)])},
                         ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({'valid': True, 'config_id': cfg['config_id'], 'config_sha256': cfg['_config_sha256'],
                      'min_req_size_bytes': min_request_bytes(), 'min_resp_size_bytes': min_response_bytes(),
                      'target_offered_load_app': offered_load_mbps(cfg),
                      'flows': flow_plan(cfg)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
