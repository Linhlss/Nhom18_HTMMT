"""TV2 workload: framing, config schema and a loopback client/server run (no Mininet needed)."""
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

from workload import framing
from workload.config import flow_plan, load, offered_load_mbps, validate
from workload.protocol import min_request_bytes, min_response_bytes

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / 'workload/configs/smoke-c1-a1.json'
EXAMPLE = ROOT / 'workload/configs/example-benchmark-4flow.json'


class _Pair:
    def __init__(self, case):
        self.a, self.b = socket.socketpair()
        case.addCleanup(self.a.close)
        case.addCleanup(self.b.close)


class FramingTests(unittest.TestCase):
    def test_roundtrip_exact_size(self):
        pair = _Pair(self)
        frame = framing.encode({'msg': 'request', 'x': 'đ'}, 1024)
        self.assertEqual(len(frame), 1024)
        pair.a.sendall(frame)
        meta, total = framing.read_frame(pair.b)
        self.assertEqual((meta['x'], meta['frame_bytes'], total), ('đ', 1024, 1024))

    def test_size_too_small_is_an_error(self):
        with self.assertRaises(framing.FrameError):
            framing.encode({'msg': 'request', 'pad': 'x' * 200}, 128)

    def test_lying_frame_bytes_is_rejected(self):
        pair = _Pair(self)
        raw = json.dumps({'frame_bytes': 999}).encode()
        pair.a.sendall(framing.HEADER.pack(len(raw), 0) + raw)
        with self.assertRaises(framing.FrameError):
            framing.read_frame(pair.b)

    def test_minimum_sizes_cover_worst_case_metadata(self):
        self.assertGreater(min_request_bytes(), 128)
        self.assertGreater(min_response_bytes(), 128)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads(SMOKE.read_text())

    def test_shipped_configs_are_valid(self):
        self.assertEqual(validate(json.loads(SMOKE.read_text())), [])
        self.assertEqual(validate(json.loads(EXAMPLE.read_text())), [])

    def test_clients_as_list_of_strings_rejected(self):
        bad = copy.deepcopy(self.cfg)
        bad['network']['clients'] = ['c1']
        self.assertTrue(any('clients[0]' in p for p in validate(bad)))

    def test_server_endpoint_string_rejected(self):
        bad = copy.deepcopy(self.cfg)
        bad['network']['servers'] = ['10.18.3.11:8000']
        self.assertTrue(any('servers[0]' in p for p in validate(bad)))

    def test_http_not_specified_in_v1(self):
        bad = dict(self.cfg, protocol='http')
        self.assertTrue(any('protocol' in p for p in validate(bad)))

    def test_size_below_metadata_rejected(self):
        bad = copy.deepcopy(self.cfg)
        bad['workload']['req_size_bytes'] = 128
        self.assertTrue(any('req_size_bytes' in p for p in validate(bad)))

    def test_wrong_ip_or_port_rejected(self):
        bad = copy.deepcopy(self.cfg)
        bad['network']['servers'][0]['ip'] = '10.18.3.12'
        bad['network']['servers'][0]['port'] = 9000
        problems = validate(bad)
        self.assertTrue(any('does not match topology' in p for p in problems))
        self.assertTrue(any('port must be 8000' in p for p in problems))

    def test_benchmark_rules(self):
        bad = json.loads(EXAMPLE.read_text())
        bad['workload']['concurrency'] = 3
        bad['execution']['warmup_sec'] = 1
        problems = validate(bad)
        self.assertTrue(any('1, 2, 4, 8' in p for p in problems))
        self.assertTrue(any('warmup_sec >= 2' in p for p in problems))

    def test_round_robin_and_offered_load(self):
        cfg = load(EXAMPLE)
        plan = flow_plan(cfg)
        self.assertEqual([f['client']['name'] for f in plan], ['c1', 'c2', 'c1', 'c2'])
        load_ = offered_load_mbps(cfg)
        self.assertAlmostEqual(load_['server_to_client_mbps'], 4 * 10 * 65536 * 8 / 1e6, places=6)


def _port_free(port):
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False


@unittest.skipUnless(_port_free(8000), 'TCP 127.0.0.1:8000 busy on this machine')
class LoopbackRunTests(unittest.TestCase):
    """End-to-end on 127.0.0.1 (loopback allowed only through NHOM18_ALLOW_LOOPBACK=1)."""

    def run_pair(self, fault='none'):
        tmp = Path(tempfile.mkdtemp())
        cfg = json.loads(SMOKE.read_text())
        cfg['network']['clients'][0]['ip'] = cfg['network']['servers'][0]['ip'] = '127.0.0.1'
        (tmp / 'cfg.json').write_text(json.dumps(cfg))
        env = dict(os.environ, NHOM18_ALLOW_LOOPBACK='1')
        srv = subprocess.Popen([sys.executable, str(ROOT / 'workload/server.py'), '--host-name', 'a1', '--bind',
                                '127.0.0.1', '--run-id', 'T', '--out', str(tmp / 'srv'), '--expect-requests', '10',
                                '--max-runtime', '20', '--fault', fault], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        cli = subprocess.run([sys.executable, str(ROOT / 'workload/client.py'), '--config', str(tmp / 'cfg.json'),
                              '--client-name', 'c1', '--run-id', 'T', '--profile', 'unknown',
                              '--out', str(tmp / 'cli')], env=env, capture_output=True, text=True, timeout=30)
        srv.communicate(timeout=30)
        return cli.returncode, srv.returncode, tmp

    def test_ten_valid_responses(self):
        crc, src, tmp = self.run_pair()
        self.assertEqual((crc, src), (0, 0))
        summary = json.loads((tmp / 'cli/client-summary.json').read_text())
        self.assertEqual(summary['status_counts'], {'OK': 10})

    def test_wrong_id_and_short_response_fail(self):
        self.assertEqual(self.run_pair('wrong-id')[0], 4)
        self.assertEqual(self.run_pair('short-response')[0], 4)


if __name__ == '__main__':
    unittest.main()
