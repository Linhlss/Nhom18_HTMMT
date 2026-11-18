"""TV3 converters and nearest-rank statistics. Fixtures are SYNTHETIC (minh họa), not measurements."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from measurement.to_csv import main as to_csv
from tools.stats import describe, percentile_nearest_rank

PING_FIXTURE = """PING 10.18.3.11 (10.18.3.11) 56(84) bytes of data.
[1700000000.000100] 64 bytes from 10.18.3.11: icmp_seq=1 ttl=62 time=5.10 ms
[1700000000.200200] 64 bytes from 10.18.3.11: icmp_seq=2 ttl=62 time=4.90 ms
[1700000000.400300] 64 bytes from 10.18.3.11: icmp_seq=4 ttl=62 time=6.00 ms

--- 10.18.3.11 ping statistics ---
4 packets transmitted, 3 received, 25% packet loss, time 601ms
rtt min/avg/max/mdev = 4.900/5.333/6.000/0.478 ms
"""


def iperf_fixture():
    def interval(start, omitted, bps):
        return {'streams': [], 'sum': {'start': start, 'end': start + 1, 'seconds': 1.0, 'bytes': int(bps / 8),
                                       'bits_per_second': bps, 'retransmits': 0, 'omitted': omitted}}
    return {'start': {'connected': [{'remote_port': 5201}], 'timestamp': {'timesecs': 1700000000},
                      'test_start': {'protocol': 'TCP', 'num_streams': 1, 'omit': 2, 'duration': 10}},
            'intervals': [interval(0, True, 1e6), interval(1, True, 1e6)] + [interval(i, False, 2e6) for i in range(10)],
            'end': {'sum_sent': {'seconds': 10.0, 'bytes': 2500000, 'bits_per_second': 2e6, 'retransmits': 1},
                    'sum_received': {'seconds': 10.0, 'bytes': 2490000, 'bits_per_second': 1.992e6}}}


def rows(path):
    with Path(path).open(encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


class StatsTests(unittest.TestCase):
    def test_nearest_rank(self):
        data = list(range(1, 21))  # 1..20
        self.assertEqual(percentile_nearest_rank(data, 95), 19)   # ceil(19.0) = 19
        self.assertEqual(percentile_nearest_rank(data, 99), 20)   # ceil(19.8) = 20
        self.assertEqual(percentile_nearest_rank(data, 50), 10)
        self.assertIsNone(percentile_nearest_rank([], 95))
        self.assertEqual(describe([])['count'], 0)
        self.assertIsNone(describe([])['mean'])


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.common = ['--run-id', 'R', '--profile', 'A', '--src', 'c1', '--dst', 'a1', '--out-dir', str(self.tmp)]

    def test_ping(self):
        raw = self.tmp / 'ping.txt'
        raw.write_text(PING_FIXTURE)
        self.assertEqual(to_csv(['ping', str(raw), *self.common]), 0)
        samples = rows(self.tmp / 'ping-samples.csv')
        self.assertEqual([r['icmp_seq'] for r in samples], ['1', '2', '4'])
        self.assertEqual(samples[0]['ts_utc'], '2023-11-14T22:13:20.000100Z')
        summary = rows(self.tmp / 'ping-summary.csv')[0]
        self.assertEqual((summary['packets_tx'], summary['packets_rx']), ('4', '3'))
        self.assertEqual(float(summary['icmp_loss_pct']), 25.0)
        self.assertEqual(summary['config_id'], '')  # unknown stays empty, never 0
        self.assertEqual(raw.read_text(), PING_FIXTURE)  # raw untouched

    def test_ping_without_summary_fails(self):
        raw = self.tmp / 'bad.txt'
        raw.write_text('connect: Network is unreachable\n')
        self.assertEqual(to_csv(['ping', str(raw), *self.common]), 2)

    def test_iperf3_excludes_omitted(self):
        raw = self.tmp / 'iperf.json'
        raw.write_text(json.dumps(iperf_fixture()))
        self.assertEqual(to_csv(['iperf3', str(raw), *self.common]), 0)
        summary = rows(self.tmp / 'iperf3-summary.csv')[0]
        self.assertEqual(summary['measured_intervals'], '10')
        self.assertEqual(float(summary['receiver_goodput_mbps']), 1.992)
        self.assertEqual(float(summary['interval_goodput_min_mbps']), 2.0)
        intervals = rows(self.tmp / 'iperf3-intervals.csv')
        self.assertEqual(sum(int(r['omitted']) for r in intervals), 2)

    def test_iperf3_error_fails(self):
        raw = self.tmp / 'err.json'
        raw.write_text(json.dumps({'error': 'unable to connect to server'}))
        self.assertEqual(to_csv(['iperf3', str(raw), *self.common]), 2)


if __name__ == '__main__':
    unittest.main()
