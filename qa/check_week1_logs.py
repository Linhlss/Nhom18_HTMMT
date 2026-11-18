#!/usr/bin/env python3
"""TV4 week-1 log check: cross-check TV2 client/server logs and TV3 raw output vs CSV.

    python3 qa/check_week1_logs.py --tv2 evidence/tv2-week1/<run> --tv3 evidence/tv3-week1/<run> \
        --out evidence/tv4-week1/<UTC>-<label>

Re-parses raw data independently of the code under review (no import of workload/ or
measurement/). Writes qa-report.json and qa-report.md. Exit 0 only when every check passes.
"""
import argparse
import csv
import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys

TOL_MS = 1e-6


def utc_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


class Report:
    def __init__(self):
        self.checks = []

    def check(self, area, name, passed, detail=''):
        self.checks.append({'area': area, 'check': name, 'passed': bool(passed), 'detail': detail})
        return passed

    @property
    def success(self):
        return bool(self.checks) and all(c['passed'] for c in self.checks)


def read_csv(path):
    with Path(path).open(encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def nearest_rank(values, p):
    data = sorted(values)
    return data[max(1, math.ceil(p / 100 * len(data))) - 1] if data else None


def check_tv2(r, d):
    area = 'TV2'
    res = json.loads((d / 'result.json').read_text())
    r.check(area, 'result.json success=true và exit-code.txt=0',
            res.get('success') is True and (d / 'exit-code.txt').read_text().strip() == '0',
            f'success={res.get("success")}')
    rows = read_csv(d / 'main/client/client-requests.csv')
    events = [json.loads(line) for line in (d / 'main/server/server-events.jsonl').read_text().splitlines() if line]
    reqs = [e for e in events if e.get('event') == 'request']
    cfg_note = res.get('config_id')
    r.check(area, 'client CSV có đúng 10 dòng, tất cả status=OK',
            len(rows) == 10 and all(x['status'] == 'OK' for x in rows),
            f'{len(rows)} dòng; status={sorted({x["status"] for x in rows})}')
    ids = [x['req_id'] for x in rows]
    r.check(area, 'req_id duy nhất, seq liên tục 0..9, cùng run_id',
            len(set(ids)) == 10 and sorted(int(x['seq']) for x in rows) == list(range(10))
            and len({x['run_id'] for x in rows}) == 1 and rows[0]['run_id'] == res.get('run_id'),
            f'run_id={rows[0]["run_id"] if rows else None}')
    r.check(area, 'server ghi nhận 10 request, tập req_id trùng client',
            len(reqs) == 10 and {e['req_id'] for e in reqs} == set(ids), f'{len(reqs)} request event')
    by_id = {e['req_id']: e for e in reqs}
    size_bad, proc_bad, order_bad = [], [], []
    for x in rows:
        e = by_id.get(x['req_id'], {})
        if not (int(x['req_bytes_sent']) == e.get('req_bytes_received') == 1024
                and int(x['resp_bytes_received']) == e.get('resp_bytes_sent') == int(x['resp_bytes_expected']) == 4096):
            size_bad.append(x['req_id'])
        if abs(float(x['server_proc_ms']) - e.get('server_proc_ms', float('nan'))) > TOL_MS:
            proc_bad.append(x['req_id'])
        if not (x['send_utc'] <= e.get('recv_utc', '') <= x['recv_utc']):
            order_bad.append(x['req_id'])
    r.check(area, 'số byte request 1024 B và response 4096 B khớp ở cả client và server (frame gồm header+JSON+padding)',
            not size_bad, f'sai: {size_bad}' if size_bad else f'config {cfg_note}: 10/10 khớp')
    r.check(area, 'server_proc_ms trong CSV client bằng log server', not proc_bad, f'sai: {proc_bad}' if proc_bad else '10/10')
    r.check(area, 'thứ tự UTC: client gửi ≤ server nhận ≤ client nhận (cùng đồng hồ VM)', not order_bad,
            f'sai: {order_bad}' if order_bad else '10/10')
    resid = [float(x['app_response_ms']) - float(x['server_proc_ms']) for x in rows]
    r.check(area, 'network_residual_est_ms = app_response_ms − server_proc_ms, không âm, residual_valid=1',
            all(abs(v - float(x['network_residual_est_ms'])) < 1e-5 and x['residual_valid'] == '1' and v >= 0
                for v, x in zip(resid, rows)), f'min={min(resid):.6f} ms' if resid else 'không có mẫu')
    needed = {'run_id', 'config_id', 'profile', 'is_warmup', 'send_utc', 'recv_utc', 'send_mono_ns', 'recv_mono_ns',
              'app_response_ms', 'server_proc_ms', 'network_residual_est_ms', 'residual_valid', 'status',
              'req_bytes_sent', 'resp_bytes_received'}
    r.check(area, 'CSV có đủ cột để tính metric theo metrics-spec §5', needed <= set(rows[0]) if rows else False,
            f'thiếu: {sorted(needed - set(rows[0]))}' if rows and not needed <= set(rows[0]) else 'đủ')
    r.check(area, 'profile/config_id tách riêng (profile=A, config_id=smoke_c1_a1_v1)',
            rows and rows[0]['profile'] == 'A' and rows[0]['config_id'] == 'smoke_c1_a1_v1',
            f'profile={rows[0]["profile"] if rows else None}, config_id={rows[0]["config_id"] if rows else None}')
    for case, expect_rc, marker in (('neg-wrong-id', 4, 'unmatched'), ('neg-short-response', 4, 'SIZE_MISMATCH'),
                                    ('neg-no-server', 3, 'CONN_ERROR')):
        rec_path = d / case / 'exec-record.json'
        if not rec_path.exists():
            r.check(area, f'negative control {case}', False, 'thiếu thư mục (chạy smoke_test.py --negative)')
            continue
        rec = json.loads(rec_path.read_text())
        summ = json.loads((d / case / 'client/client-summary.json').read_text())
        seen = bool(summ.get('unmatched_responses')) if marker == 'unmatched' else summ['status_counts'].get(marker, 0) > 0
        r.check(area, f'negative control {case}: client trả mã {expect_rc} và log đúng loại lỗi',
                rec.get('client_returncode') == expect_rc and seen,
                f'rc={rec.get("client_returncode")}, status={summ["status_counts"]}')


PING_LINE = re.compile(r'icmp_seq=(\d+) ttl=\d+ time=([\d.]+) ms')
PING_SUM = re.compile(r'(\d+) packets transmitted, (\d+) received')
PING_RTT = re.compile(r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms')


def check_tv3(r, d):
    area = 'TV3'
    res = json.loads((d / 'result.json').read_text())
    r.check(area, 'result.json success=true, profile A, exit-code 0',
            res.get('success') is True and res.get('profile') == 'A'
            and (d / 'exit-code.txt').read_text().strip() == '0', f'checks={res.get("checks")}')
    raw = (d / 'ping-c1-a1.txt').read_text()
    raw_samples = [(int(s), float(t)) for s, t in PING_LINE.findall(raw)]
    tx, rx = map(int, PING_SUM.search(raw).groups())
    samples = read_csv(d / 'ping-samples.csv')
    summ = read_csv(d / 'ping-summary.csv')[0]
    r.check(area, 'ping raw: 20 gói gửi/20 nhận, CSV packets_tx/rx khớp',
            tx == 20 and rx == 20 and int(summ['packets_tx']) == tx and int(summ['packets_rx']) == rx,
            f'raw {tx}/{rx}; CSV {summ["packets_tx"]}/{summ["packets_rx"]}')
    csv_samples = [(int(x['icmp_seq']), float(x['icmp_rtt_ms'])) for x in samples]
    r.check(area, 'từng mẫu RTT trong ping-samples.csv khớp dòng raw (seq, time)', csv_samples == raw_samples,
            f'{len(csv_samples)} mẫu CSV / {len(raw_samples)} dòng raw; ví dụ seq={raw_samples[0][0]} '
            f'raw={raw_samples[0][1]} ms, CSV={csv_samples[0][1] if csv_samples else None} ms' if raw_samples else '')
    loss = (tx - rx) / tx * 100
    r.check(area, 'icmp_loss_pct tính từ gửi/nhận', abs(float(summ['icmp_loss_pct']) - loss) < 1e-9,
            f'{summ["icmp_loss_pct"]} %')
    rtts = [t for _, t in raw_samples]
    mn, avg, mx, _ = map(float, PING_RTT.search(raw).groups())
    r.check(area, 'min/mean/max CSV khớp dòng tổng kết ping (avg làm tròn 0,001 ms)',
            float(summ['icmp_rtt_min_ms']) == mn and float(summ['icmp_rtt_max_ms']) == mx
            and abs(float(summ['icmp_rtt_mean_ms']) - avg) <= 0.0015,
            f'ping {mn}/{avg}/{mx}; CSV {summ["icmp_rtt_min_ms"]}/{summ["icmp_rtt_mean_ms"]}/{summ["icmp_rtt_max_ms"]}')
    r.check(area, 'p95/p99 nearest-rank tính lại khớp CSV (n=20)',
            float(summ['icmp_rtt_p95_ms']) == nearest_rank(rtts, 95) and float(summ['icmp_rtt_p99_ms']) == nearest_rank(rtts, 99),
            f'p95={nearest_rank(rtts, 95)}, p99={nearest_rank(rtts, 99)}, n={len(rtts)}')
    data = json.loads((d / 'iperf3-c1-a1-client.json').read_text())
    isum = read_csv(d / 'iperf3-summary.csv')[0]
    test = data['start']['test_start']
    r.check(area, 'iperf3: TCP, 1 luồng, -t 10, -O 2, cổng 5201',
            test.get('protocol') == 'TCP' and test.get('num_streams') == 1 and test.get('duration') == 10
            and test.get('omit') == 2 and data['start']['connected'][0]['remote_port'] == 5201,
            f'protocol={test.get("protocol")}, streams={test.get("num_streams")}, t={test.get("duration")}, O={test.get("omit")}')
    recv_mbps = data['end']['sum_received']['bits_per_second'] / 1e6
    r.check(area, 'receiver goodput CSV = end.sum_received.bits_per_second/1e6 trong raw JSON',
            abs(float(isum['receiver_goodput_mbps']) - recv_mbps) < 1e-6, f'raw={recv_mbps:.6f} Mbps; CSV={isum["receiver_goodput_mbps"]}')
    meas = [i['sum'] for i in data['intervals'] if not i['sum'].get('omitted')]
    secs = sum(i['seconds'] for i in meas)
    r.check(area, 'khoảng đo không tính phần omit ≈ 10 s', abs(secs - 10) <= 0.25 and
            abs(float(isum['measured_seconds_from_intervals']) - secs) < 1e-6, f'{secs:.3f} s, {len(meas)} interval')
    for name in ('ping-c1-a1.txt', 'iperf3-c1-a1-client.json'):
        csv_name = 'ping-summary.csv' if name.startswith('ping') else 'iperf3-summary.csv'
        recorded = read_csv(d / csv_name)[0]['raw_sha256']
        actual = hashlib.sha256((d / name).read_bytes()).hexdigest()
        r.check(area, f'raw {name} không bị sửa sau khi chuyển CSV (sha256)', recorded == actual, actual[:16])


def to_markdown(report, args, started):
    lines = [f'# Kết quả kiểm tra log tuần 1 (TV4)', '',
             f'- Thời điểm chạy (UTC): {started}', f'- TV2 evidence: `{args.tv2}`', f'- TV3 evidence: `{args.tv3}`',
             f'- Kết luận: **{"ĐẠT" if report.success else "KHÔNG ĐẠT"}** '
             f'({sum(c["passed"] for c in report.checks)}/{len(report.checks)} kiểm tra)', '',
             '| Phần | Kiểm tra | Kết quả | Chi tiết |', '|---|---|---|---|']
    for c in report.checks:
        detail = str(c['detail']).replace('|', '\\|')
        lines.append(f'| {c["area"]} | {c["check"]} | {"ĐẠT" if c["passed"] else "KHÔNG ĐẠT"} | {detail} |')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--tv2', required=True, type=Path)
    p.add_argument('--tv3', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args(argv)
    started = utc_iso()
    report = Report()
    for area, fn, path in (('TV2', check_tv2, args.tv2), ('TV3', check_tv3, args.tv3)):
        try:
            fn(report, path)
        except Exception as error:  # a crash in the checker is a failed check, never a pass
            report.check(area, 'đọc được đủ file minh chứng', False, f'{type(error).__name__}: {error}')
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'qa-report.json').write_text(json.dumps(
        {'started_utc': started, 'tv2': str(args.tv2), 'tv3': str(args.tv3), 'success': report.success,
         'checks': report.checks}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (args.out / 'qa-report.md').write_text(to_markdown(report, args, started), encoding='utf-8')
    (args.out / 'exit-code.txt').write_text('0\n' if report.success else '1\n')
    for c in report.checks:
        print(('PASS ' if c['passed'] else 'FAIL ') + f'[{c["area"]}] {c["check"]}')
    return 0 if report.success else 1


if __name__ == '__main__':
    sys.exit(main())
