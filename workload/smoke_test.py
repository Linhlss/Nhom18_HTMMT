#!/usr/bin/python3
"""TV2 week-1 smoke test: c1 -> a1, TCP/8000, 10 framed requests through TV1's running testbed.

Run inside the Ubuntu VM after `sudo /usr/bin/python3 control/networkctl.py start --profile A`:

    sudo /usr/bin/python3 workload/smoke_test.py --label tv2-smoke [--negative]

Evidence: evidence/tv2-week1/<UTC>-<label>/ (run_id = folder name). Exit 0 only when the main
run has 10/10 valid responses with client and server exit code 0 and, with --negative, every
negative control fails with its expected non-zero exit code.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.evidence import (chown_to_sudo_user, environment, exec_argv, make_run_dir, networkctl,  # noqa: E402
                            require_vm_root, save_json, source_manifest, utc_iso)
from workload.config import load  # noqa: E402

PY = '/usr/bin/python3'


def wait_listening(host, port, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = networkctl('exec', '--timeout', '5', host, '--', 'ss', '-ltnH', f'sport = :{port}')
        if f':{port}' in r['result'].get('stdout', ''):
            return True
        time.sleep(0.2)
    return False


def one_run(out, run_id, cfg_path, cfg, profile, case):
    """case: dict(name, server_fault, start_server, expect_client_rc, expect_server_rc)."""
    case_dir = out / case['name']
    case_dir.mkdir()
    server = cfg['network']['servers'][0]
    client = cfg['network']['clients'][0]
    n = cfg['execution']['max_requests_per_flow'] * cfg['workload']['concurrency']
    case_run_id = run_id if case['name'] == 'main' else f'{run_id}-{case["name"]}'
    record = {'case': case['name'], 'run_id': case_run_id, 'started_utc': utc_iso(), **case}
    srv = None
    if case['start_server']:
        srv_argv = exec_argv(server['name'], [PY, 'workload/server.py', '--host-name', server['name'],
                                              '--port', str(server['port']), '--run-id', case_run_id,
                                              '--out', str(case_dir / 'server'), '--expect-requests', str(n),
                                              '--max-runtime', '40', '--fault', case['server_fault'],
                                              '--fault-seq', '3'], 50)
        record['server_command'] = srv_argv[1:]
        srv = subprocess.Popen(srv_argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        record['server_listening_seen'] = wait_listening(server['name'], server['port'])
    cli_argv = exec_argv(client['name'], [PY, 'workload/client.py', '--config', cfg_path, '--client-name',
                                          client['name'], '--run-id', case_run_id, '--profile', profile,
                                          '--out', str(case_dir / 'client'),
                                          '--connect-retry-sec', '3' if case['start_server'] else '2'], 60)
    record['client_command'] = cli_argv[1:]
    cli = subprocess.run(cli_argv, text=True, capture_output=True, timeout=80)
    record['client_exec'] = json.loads(cli.stdout) if cli.stdout.strip() else {'raw_stderr': cli.stderr}
    if srv:
        try:
            s_out, s_err = srv.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            srv.kill()
            s_out, s_err = srv.communicate()
        record['server_exec'] = json.loads(s_out) if s_out.strip() else {'raw_stderr': s_err}
    client_rc = record['client_exec'].get('returncode')
    server_rc = record.get('server_exec', {}).get('returncode')
    record['client_returncode'], record['server_returncode'] = client_rc, server_rc
    record['passed'] = client_rc == case['expect_client_rc'] and \
        (case['expect_server_rc'] is None or server_rc == case['expect_server_rc'])
    record['finished_utc'] = utc_iso()
    save_json(case_dir / 'exec-record.json', record)
    print(('PASS ' if record['passed'] else 'FAIL ') + f'{case["name"]}: client rc={client_rc} '
          f'(expect {case["expect_client_rc"]}), server rc={server_rc} (expect {case["expect_server_rc"]})',
          flush=True)
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--label', default='tv2-smoke')
    p.add_argument('--config', default='workload/configs/smoke-c1-a1.json')
    p.add_argument('--negative', action='store_true', help='also run negative controls (expected failures)')
    args = p.parse_args()
    require_vm_root()
    cfg = load(ROOT / args.config)
    run_id, out = make_run_dir('tv2-week1', args.label)
    result = {'run_id': run_id, 'config_id': cfg['config_id'], 'config_sha256': cfg['_config_sha256'],
              'started_utc': utc_iso(), 'success': False, 'cases': []}
    try:
        status = networkctl('status')
        save_json(out / 'network-status.json', status)
        if not status['result'].get('success'):
            raise RuntimeError('testbed is not running: start it with networkctl start --profile A')
        profile = status['result'].get('profile') or 'unknown'
        result['profile'] = profile
        save_json(out / 'environment.json', environment({'runner': 'workload/smoke_test.py', 'argv': sys.argv,
                                                         'network_session_id': status['result'].get('session_id'),
                                                         'network_config_hash': status['result'].get('config_hash')}))
        save_json(out / 'source-manifest.json', source_manifest(['workload', 'tools', 'control', 'topology']))
        cases = [{'name': 'main', 'server_fault': 'none', 'start_server': True,
                  'expect_client_rc': 0, 'expect_server_rc': 0}]
        if args.negative:
            cases += [
                {'name': 'neg-wrong-id', 'server_fault': 'wrong-id', 'start_server': True,
                 'expect_client_rc': 4, 'expect_server_rc': 0},
                {'name': 'neg-short-response', 'server_fault': 'short-response', 'start_server': True,
                 'expect_client_rc': 4, 'expect_server_rc': 0},
                {'name': 'neg-no-server', 'server_fault': 'none', 'start_server': False,
                 'expect_client_rc': 3, 'expect_server_rc': None},
            ]
        for case in cases:
            result['cases'].append(one_run(out, run_id, args.config, cfg, profile, case))
        main_case = result['cases'][0]
        summary = json.loads((out / 'main/client/client-summary.json').read_text())
        result['main_status_counts'] = summary['status_counts']
        result['main_valid_responses'] = summary['status_counts'].get('OK', 0)
        result['main_requests_expected'] = summary['requests_expected']
        result['load_sustained'] = summary['load_check']['load_sustained']
        result['success'] = all(c['passed'] for c in result['cases']) and \
            result['main_valid_responses'] == result['main_requests_expected'] == 10 and main_case['passed']
    except Exception as error:  # record and fail; never convert to PASS
        result['error'] = f'{type(error).__name__}: {error}'
        print(f'FAIL {result["error"]}', flush=True)
    finally:
        result['finished_utc'] = utc_iso()
        save_json(out / 'result.json', result)
        (out / 'exit-code.txt').write_text('0\n' if result['success'] else '1\n')
        chown_to_sudo_user(out)
        print('EVIDENCE ' + str(out.relative_to(ROOT)), flush=True)
    return 0 if result['success'] else 1


if __name__ == '__main__':
    sys.exit(main())
