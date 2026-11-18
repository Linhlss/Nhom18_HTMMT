#!/usr/bin/python3
"""TV3 week-1 diagnostic probe on profile A (docs/metrics-spec.md §8).

1. ping c1 -> a1: 20 packets, interval 0.2 s (network idle: no iperf3 running).
2. iperf3 TCP c1 -> a1:5201, 1 stream, 10 s measured after omitting the first 2 s (-t 10 -O 2).
Raw output is saved untouched; measurement/to_csv.py converts it to CSV.

    sudo /usr/bin/python3 measurement/week1_probe.py --label tv3-probe

This is a diagnostic measurement, not an AI-inference benchmark. Exit 0 only when the testbed
is on profile A, both tools exit 0, ping receives 20/20 and both conversions succeed.
"""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from measurement.to_csv import main as to_csv  # noqa: E402
from tools.evidence import (chown_to_sudo_user, environment, exec_argv, make_run_dir, networkctl,  # noqa: E402
                            require_vm_root, save_json, source_manifest, utc_iso)
from topology.model import IPS  # noqa: E402

SRC, DST, PORT = 'c1', 'a1', 5201
PING_ARGV = ['ping', '-D', '-n', '-c', '20', '-i', '0.2', '-W', '2', IPS[DST]]
IPERF_SERVER_ARGV = ['iperf3', '-s', '-1', '-p', str(PORT), '-J']
IPERF_CLIENT_ARGV = ['iperf3', '-c', IPS[DST], '-p', str(PORT), '-P', '1', '-t', '10', '-O', '2', '-J']


def run_exec(host, argv, timeout):
    full = exec_argv(host, argv, timeout)
    p = subprocess.run(full, text=True, capture_output=True, timeout=timeout + 20)
    data = json.loads(p.stdout) if p.stdout.strip() else {'success': False, 'cli_stderr': p.stderr}
    return full[1:], data


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--label', default='tv3-probe')
    args = p.parse_args()
    require_vm_root()
    run_id, out = make_run_dir('tv3-week1', args.label)
    result = {'run_id': run_id, 'started_utc': utc_iso(), 'success': False, 'checks': {}}
    try:
        status = networkctl('status')
        save_json(out / 'network-status.json', status)
        profile = status['result'].get('profile')
        result['profile'] = profile
        result['checks']['testbed_running_profile_A'] = bool(status['result'].get('success')) and profile == 'A'
        if not result['checks']['testbed_running_profile_A']:
            raise RuntimeError(f'need a running testbed on profile A (got {profile!r})')
        if status['result'].get('active_commands'):
            raise RuntimeError('other workload commands are running; the probe needs an otherwise idle testbed')
        save_json(out / 'environment.json', environment({'runner': 'measurement/week1_probe.py', 'argv': sys.argv,
                                                         'network_session_id': status['result'].get('session_id'),
                                                         'network_config_hash': status['result'].get('config_hash')}))
        save_json(out / 'source-manifest.json', source_manifest(['measurement', 'tools', 'control', 'topology']))

        # 1) ping while nothing else runs on the testbed
        cmd, ping = run_exec(SRC, PING_ARGV, 30)
        (out / 'ping-c1-a1.txt').write_text(ping.get('stdout', ''), encoding='utf-8')
        save_json(out / 'ping-exec.json', {'command': cmd, 'started_note': 'raw stdout saved to ping-c1-a1.txt',
                                           **{k: v for k, v in ping.items() if k != 'stdout'}})
        result['checks']['ping_exit_0'] = ping.get('returncode') == 0

        # 2) iperf3 server one-off on a1, client on c1
        srv_cmd = exec_argv(DST, IPERF_SERVER_ARGV, 60)
        srv = subprocess.Popen(srv_cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        listening = False
        for _ in range(50):
            r = networkctl('exec', '--timeout', '5', DST, '--', 'ss', '-ltnH', f'sport = :{PORT}')
            if f':{PORT}' in r['result'].get('stdout', ''):
                listening = True
                break
            time.sleep(0.2)
        result['checks']['iperf3_server_listening'] = listening
        cmd, client = run_exec(SRC, IPERF_CLIENT_ARGV, 40)
        (out / 'iperf3-c1-a1-client.json').write_text(client.get('stdout', ''), encoding='utf-8')
        save_json(out / 'iperf3-client-exec.json', {'command': cmd, **{k: v for k, v in client.items() if k != 'stdout'}})
        s_out, s_err = srv.communicate(timeout=70)
        server = json.loads(s_out) if s_out.strip() else {'success': False, 'cli_stderr': s_err}
        (out / 'iperf3-a1-server.json').write_text(server.get('stdout', ''), encoding='utf-8')
        save_json(out / 'iperf3-server-exec.json', {'command': srv_cmd[1:], **{k: v for k, v in server.items() if k != 'stdout'}})
        result['checks']['iperf3_client_exit_0'] = client.get('returncode') == 0
        result['checks']['iperf3_server_exit_0'] = server.get('returncode') == 0

        # 3) conversion (raw stays untouched; CSV written next to it)
        common = ['--run-id', run_id, '--profile', profile, '--src', SRC, '--dst', DST, '--out-dir', str(out)]
        result['checks']['ping_csv_ok'] = to_csv(['ping', str(out / 'ping-c1-a1.txt'), *common]) == 0
        result['checks']['iperf3_csv_ok'] = to_csv(['iperf3', str(out / 'iperf3-c1-a1-client.json'), *common]) == 0
        if result['checks']['ping_csv_ok']:
            with (out / 'ping-summary.csv').open(encoding='utf-8', newline='') as fh:
                row = next(csv.DictReader(fh))
            result['checks']['ping_20_of_20'] = row['packets_tx'] == '20' and row['packets_rx'] == '20'
        result['success'] = all(result['checks'].values())
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
        print(f'FAIL {result["error"]}', flush=True)
    finally:
        result['finished_utc'] = utc_iso()
        result['commands'] = {'ping': PING_ARGV, 'iperf3_server': IPERF_SERVER_ARGV, 'iperf3_client': IPERF_CLIENT_ARGV}
        save_json(out / 'result.json', result)
        (out / 'exit-code.txt').write_text('0\n' if result['success'] else '1\n')
        chown_to_sudo_user(out)
        for k, v in result['checks'].items():
            print(('PASS ' if v else 'FAIL ') + k, flush=True)
        print('EVIDENCE ' + str(out.relative_to(ROOT)), flush=True)
    return 0 if result['success'] else 1


if __name__ == '__main__':
    sys.exit(main())
