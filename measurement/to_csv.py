#!/usr/bin/env python3
"""Convert raw ping / iperf3 output to CSV without editing the raw files (TV3, docs/metrics-spec.md).

    python3 measurement/to_csv.py ping   RAW.txt  --run-id R --profile A --src c1 --dst a1 --out-dir DIR
    python3 measurement/to_csv.py iperf3 RAW.json --run-id R --profile A --src c1 --dst a1 --out-dir DIR

ping:   expects `ping -D -n` output (Linux iputils). Writes ping-samples.csv and ping-summary.csv.
iperf3: expects `iperf3 -J` client output. Writes iperf3-intervals.csv and iperf3-summary.csv.
Missing values are written as empty cells, never 0. Exit 0 on success, 2 on unparseable input.
"""
import argparse
import csv
import datetime
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.evidence import sha256_file  # noqa: E402
from tools.stats import describe  # noqa: E402

REPLY = re.compile(r'^\[(?P<epoch>\d+\.\d+)\] (?P<bytes>\d+) bytes from (?P<ip>[\d.]+): '
                   r'icmp_seq=(?P<seq>\d+) ttl=(?P<ttl>\d+) time=(?P<rtt>[\d.]+) ms$')
TX_RX = re.compile(r'^(?P<tx>\d+) packets transmitted, (?P<rx>\d+) received'
                   r'(?:, \+\d+ (?:duplicates|corrupted|errors))*, (?P<loss>[\d.]+)% packet loss')
RTT_LINE = re.compile(r'^rtt min/avg/max/mdev = (?P<min>[\d.]+)/(?P<avg>[\d.]+)/(?P<max>[\d.]+)/(?P<mdev>[\d.]+) ms$')


class ParseError(ValueError):
    pass


def iso_from_epoch(epoch):
    return datetime.datetime.fromtimestamp(float(epoch), datetime.timezone.utc) \
        .isoformat(timespec='microseconds').replace('+00:00', 'Z')


def write_csv(path, columns, rows):
    with Path(path).open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        for row in rows:
            w.writerow({k: ('' if row.get(k) is None else row.get(k)) for k in columns})


def parse_ping(text):
    samples, tx_rx, rtt = [], None, None
    for line_no, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if m := REPLY.match(line):
            samples.append({'raw_line': line_no, 'icmp_seq': int(m['seq']), 'ts_utc': iso_from_epoch(m['epoch']),
                            'reply_bytes': int(m['bytes']), 'ttl': int(m['ttl']), 'icmp_rtt_ms': float(m['rtt']),
                            'reply_ip': m['ip']})
        elif m := TX_RX.match(line):
            tx_rx = m
        elif m := RTT_LINE.match(line):
            rtt = m
    if tx_rx is None:
        raise ParseError('ping summary line "N packets transmitted, M received" not found')
    return samples, tx_rx, rtt


def ping_to_csv(raw, args):
    text = Path(raw).read_text(encoding='utf-8')
    samples, tx_rx, rtt = parse_ping(text)
    base = {'run_id': args.run_id, 'config_id': args.config_id, 'profile': args.profile,
            'src_host': args.src, 'dst_host': args.dst}
    cols = ['run_id', 'config_id', 'profile', 'src_host', 'dst_host', 'sample_type', 'icmp_seq', 'ts_utc',
            'icmp_rtt_ms', 'ttl', 'reply_bytes', 'raw_file', 'raw_line']
    rows = [{**base, 'sample_type': 'icmp_echo_reply', **s, 'raw_file': Path(raw).name} for s in samples]
    write_csv(Path(args.out_dir) / 'ping-samples.csv', cols, rows)
    tx, rx = int(tx_rx['tx']), int(tx_rx['rx'])
    stats = describe([s['icmp_rtt_ms'] for s in samples])
    summary = {
        **base, 'packets_tx': tx, 'packets_rx': rx,
        'icmp_loss_pct': round((tx - rx) / tx * 100, 6) if tx else None,
        'ping_reported_loss_pct': float(tx_rx['loss']),
        'rtt_sample_count': stats['count'],
        'icmp_rtt_min_ms': stats['min'], 'icmp_rtt_mean_ms': round(stats['mean'], 6) if stats['mean'] is not None else None,
        'icmp_rtt_p50_ms': stats['p50'], 'icmp_rtt_p95_ms': stats['p95'], 'icmp_rtt_p99_ms': stats['p99'],
        'icmp_rtt_max_ms': stats['max'],
        'ping_reported_min_ms': float(rtt['min']) if rtt else None,
        'ping_reported_avg_ms': float(rtt['avg']) if rtt else None,
        'ping_reported_max_ms': float(rtt['max']) if rtt else None,
        'ping_reported_mdev_ms': float(rtt['mdev']) if rtt else None,
        'percentile_method': 'nearest-rank', 'first_sample_utc': samples[0]['ts_utc'] if samples else None,
        'last_sample_utc': samples[-1]['ts_utc'] if samples else None,
        'raw_file': Path(raw).name, 'raw_sha256': sha256_file(raw),
    }
    write_csv(Path(args.out_dir) / 'ping-summary.csv', list(summary), [summary])
    return summary


def iperf3_to_csv(raw, args):
    try:
        data = json.loads(Path(raw).read_text(encoding='utf-8'))
    except json.JSONDecodeError as error:
        raise ParseError(f'iperf3 output is not JSON: {error}') from error
    if data.get('error'):
        raise ParseError(f'iperf3 reported error: {data["error"]}')
    start, end = data.get('start', {}), data.get('end', {})
    test = start.get('test_start', {})
    epoch = start.get('timestamp', {}).get('timesecs')
    base = {'run_id': args.run_id, 'config_id': args.config_id, 'profile': args.profile,
            'src_host': args.src, 'dst_host': args.dst}
    rows = []
    for i, interval in enumerate(data.get('intervals', [])):
        s = interval['sum']
        span = s['end'] - s['start']
        # iperf3 3.16 resets its time base when -O ends; the first interval after the omit
        # period can report seconds (~2 s) inconsistent with end-start. Keep the raw values,
        # flag the interval and do not use it for per-interval min/max (docs/metrics-spec.md §8).
        suspect = abs(span - s['seconds']) > 0.05
        rows.append({**base, 'interval_index': i, 'start_s': s['start'], 'end_s': s['end'],
                     'seconds': s['seconds'], 'seconds_end_minus_start': round(span, 6),
                     'timing_suspect': int(suspect), 'omitted': int(bool(s.get('omitted'))),
                     'bytes': s['bytes'], 'goodput_mbps': round(s['bits_per_second'] / 1e6, 6),
                     'retransmits': s.get('retransmits'), 'raw_file': Path(raw).name})
    write_csv(Path(args.out_dir) / 'iperf3-intervals.csv',
              ['run_id', 'config_id', 'profile', 'src_host', 'dst_host', 'interval_index', 'start_s', 'end_s',
               'seconds', 'seconds_end_minus_start', 'timing_suspect', 'omitted', 'bytes', 'goodput_mbps',
               'retransmits', 'raw_file'], rows)
    sent, received = end.get('sum_sent', {}), end.get('sum_received', {})
    if not received:
        raise ParseError('end.sum_received missing')
    measured = [r for r in rows if not r['omitted']]
    reliable = [r for r in measured if not r['timing_suspect']]
    measured_bytes = sum(r['bytes'] for r in measured)
    summary = {
        **base, 'protocol': test.get('protocol'), 'parallel_streams': test.get('num_streams'),
        'omit_s': test.get('omit'), 'duration_s_requested': test.get('duration'),
        'test_start_utc': iso_from_epoch(epoch) if epoch else None,
        'measured_intervals': len(measured), 'timing_suspect_intervals': len(measured) - len(reliable),
        'measured_bytes_from_intervals': measured_bytes,
        'interval_bytes_match_sender': int(measured_bytes == sent.get('bytes')),
        'sender_seconds': sent.get('seconds'), 'sender_bytes': sent.get('bytes'),
        'sender_goodput_mbps': round(sent['bits_per_second'] / 1e6, 6) if sent else None,
        'tcp_retransmits': sent.get('retransmits'),
        'receiver_seconds': received.get('seconds'), 'receiver_bytes': received.get('bytes'),
        'receiver_goodput_mbps': round(received['bits_per_second'] / 1e6, 6),
        'interval_goodput_min_mbps': min((r['goodput_mbps'] for r in reliable), default=None),
        'interval_goodput_max_mbps': max((r['goodput_mbps'] for r in reliable), default=None),
        'measurement_window_note': 'window = sender_seconds/receiver_seconds from iperf3 end.sum_*; '
                                   'interval start/end are relative to the post-omit time base',
        'metric_note': 'iperf3 TCP payload goodput, not interface throughput; includes no headers',
        'raw_file': Path(raw).name, 'raw_sha256': sha256_file(raw),
    }
    write_csv(Path(args.out_dir) / 'iperf3-summary.csv', list(summary), [summary])
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('kind', choices=['ping', 'iperf3'])
    p.add_argument('raw')
    p.add_argument('--run-id', required=True)
    p.add_argument('--config-id', default=None, help='workload config_id; empty for diagnostic probes')
    p.add_argument('--profile', required=True)
    p.add_argument('--src', required=True)
    p.add_argument('--dst', required=True)
    p.add_argument('--out-dir', required=True)
    args = p.parse_args(argv)
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    try:
        summary = (ping_to_csv if args.kind == 'ping' else iperf3_to_csv)(args.raw, args)
    except (OSError, ParseError, KeyError, TypeError) as error:
        print(json.dumps({'success': False, 'error': f'{type(error).__name__}: {error}'}))
        return 2
    print(json.dumps({'success': True, 'summary': summary}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
