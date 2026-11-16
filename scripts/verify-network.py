#!/usr/bin/python3
"""Real VM acceptance tests, evidence and failure exit codes for TV1's network layer."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from control.networkctl import request, SOCKET
from topology.model import HOSTS, IPS, LINKS, SWITCHES, config_hash, flow_signature


def command(argv, timeout=60, check=True):
    p = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f'{argv!r}: {p.returncode}: {p.stderr} {p.stdout}')
    return p


class Check:
    def __init__(self, output):
        self.out = output
        self.cases = []
        self.pool = ThreadPoolExecutor(max_workers=8)

    def save(self, name, value):
        (self.out / name).write_text(json.dumps(value, indent=2) + '\n')

    def assert_case(self, name, passed, details=None):
        self.cases.append({'name': name, 'success': bool(passed), 'details': details})
        print(('PASS ' if passed else 'FAIL ') + name, flush=True)
        if not passed:
            raise RuntimeError(f'{name}: {details}')

    def ctl(self, action, **kwargs):
        return request({'action': action, **kwargs}, timeout=120)

    def host(self, host, argv, timeout=25):
        return request({'action': 'exec', 'host': host, 'argv': argv, 'timeout': timeout}, timeout=timeout+10)

    def start(self, profile):
        p = command([sys.executable, str(ROOT/'control/networkctl.py'), 'start', '--profile', profile])
        return json.loads(p.stdout)

    def apply(self, profile):
        value = self.ctl('apply', profile=profile, decision='apply', confirmed=True, actor='acceptance-test')
        self.assert_case('apply-'+profile, value.get('success'), value.get('error'))
        return value

    def flows(self):
        return {s: command(['ovs-ofctl', '-O', 'OpenFlow13', 'dump-flows', s]).stdout for s in SWITCHES}

    def counter(self):
        # OVSDB Interface.statistics is periodically refreshed and can be stale
        # for a short probe. Read the kernel interface counters directly instead.
        data = json.loads(command(['ip', '-s', '-j', 'link', 'show']).stdout)
        result = {}
        for item in data:
            name = item['ifname'].split('@', 1)[0]
            if name.startswith(('leaf', 'spine')) and '-eth' in name:
                stats = item.get('stats64', item.get('stats', {}))
                result[name] = {f'{direction}_{key}': stats[direction][key]
                                for direction in ('rx', 'tx') for key in ('bytes', 'packets', 'errors', 'dropped')}
        return result

    def path_probe(self, profile, repeat):
        tag = f'{profile.lower()}-{repeat}'
        before = self.counter()
        captures = []
        try:
            for spine in ('spine1', 'spine2'):
                log = (self.out/f'{tag}-{spine}-capture.log').open('w')
                p = subprocess.Popen(['tcpdump', '-U', '-n', '-i', f'{spine}-eth1', '-w',
                                      str(self.out/f'{tag}-{spine}.pcap'), 'icmp'],
                                     stdout=subprocess.DEVNULL, stderr=log)
                captures.append((spine, p, log))
            time.sleep(0.5)
            if any(p.poll() is not None for _, p, _ in captures):
                raise RuntimeError('tcpdump did not start')
            futures = [self.pool.submit(self.host, client,
                       ['ping', '-n', '-c', '40', '-i', '0.02', '-s', '1200', '-W', '2', IPS[server]])
                       for client, server in [('c1', 'a1'), ('c2', 'a2')]]
            pings = [f.result() for f in futures]
        finally:
            for _, p, log in captures:
                if p.poll() is None:
                    p.send_signal(signal.SIGINT)
                    p.wait(timeout=5)
                log.close()
        after = self.counter()
        observed = {}
        for spine in ('spine1', 'spine2'):
            pcap = self.out/f'{tag}-{spine}.pcap'
            observed[spine] = {}
            for client in ('c1', 'c2'):
                decode = command(['tcpdump', '-nn', '-r', str(pcap), 'icmp', 'and', 'host', IPS[client]])
                observed[spine][client] = len(decode.stdout.splitlines())
                (self.out/f'{tag}-{spine}-{client}.txt').write_text(decode.stdout)
        expected = {'spine1': {'c1': True, 'c2': profile == 'A'},
                    'spine2': {'c1': False, 'c2': profile == 'B'}}
        correct = all((observed[s][c] > 0) == expected[s][c] for s in expected for c in expected[s])
        used = ('spine1',) if profile == 'A' else ('spine1', 'spine2')
        deltas = {s: {key: after[f'{s}-eth1'].get(key, 0)-before[f'{s}-eth1'].get(key, 0)
                      for key in ('rx_bytes', 'tx_bytes', 'rx_packets', 'tx_packets')} for s in ('spine1', 'spine2')}
        correct = correct and all(deltas[s]['rx_bytes'] > 0 and deltas[s]['tx_bytes'] > 0 for s in used)
        def zero_loss(p):
            match = re.search(r'(\d+) packets transmitted, (\d+) received,.*?([\d.]+)% packet loss', p.get('stdout', ''))
            return p.get('success') and bool(match) and match[1] == match[2] == '40' and float(match[3]) == 0
        correct = correct and all(zero_loss(p) for p in pings)
        evidence = {'profile': profile, 'observed_icmp_packets': observed, 'counter_delta': deltas,
                    'pings': pings, 'before_counters': before, 'after_counters': after}
        self.save(f'{tag}-paths.json', evidence)
        self.assert_case(f'path-{tag}', correct, observed)

    def firewall(self):
        probe = str(ROOT/'tests/network_probe.py')
        server = self.pool.submit(self.host, 'a1', [sys.executable, probe, 'server', '--duration', '8'], 15)
        for _ in range(30):
            listening = self.host('a1', ['ss', '-ltn'])
            if ':8000' in listening.get('stdout', '') and ':9000' in listening.get('stdout', ''):
                break
            time.sleep(0.1)
        self.assert_case('probe-listens-on-allowed-and-blocked-ports', ':8000' in listening['stdout'] and ':9000' in listening['stdout'])
        before = self.host('fw', ['iptables', '-nvxL', 'FORWARD'])
        allowed = [self.host(c, [sys.executable, probe, 'client', IPS['a1'], '8000']) for c in ('c1', 'c2')]
        blocked = [self.host(c, [sys.executable, probe, 'client', IPS['a1'], '9000']) for c in ('c1', 'c2')]
        after = self.host('fw', ['iptables', '-nvxL', 'FORWARD'])
        signatures = {s: flow_signature(d) for s, d in self.flows().items()}
        refused = self.ctl('apply', profile='B', decision='apply', confirmed=True, actor='busy-test')
        unchanged = signatures == {s: flow_signature(d) for s, d in self.flows().items()}
        self.assert_case('apply-refuses-running-workload', not refused.get('success') and unchanged)
        self.assert_case('probe-server-exits', server.result().get('success'))
        def drops(text):
            return sum(int(line.split()[0]) for line in text.splitlines() if len(line.split()) > 2 and line.split()[2] == 'DROP')
        self.save('firewall.json', {'allowed': allowed, 'blocked': blocked, 'before': before, 'after': after,
                                    'busy_apply': refused})
        self.assert_case('firewall-allows-8000-blocks-listening-9000',
                         all(p.get('success') for p in allowed) and all(not p.get('success') for p in blocked)
                         and drops(after['stdout']) > drops(before['stdout']))

    def capacity(self, profile):
        self.apply(profile)
        before = self.counter()
        servers = [self.pool.submit(self.host, s, ['iperf3', '-s', '-1', '-p', '5201', '-J'], 20) for s in ('a1', 'a2')]
        time.sleep(0.4)
        clients = [self.pool.submit(self.host, c, ['iperf3', '-c', IPS[s], '-p', '5201', '-t', '5', '-O', '1', '-P', '4', '-J'], 20)
                   for c, s in [('c1', 'a1'), ('c2', 'a2')]]
        results = [f.result() for f in clients]
        server_results = [f.result() for f in servers]
        after = self.counter()
        throughput = sum(json.loads(r['stdout'])['end']['sum_received']['bits_per_second'] for r in results)/1e6
        evidence = {'purpose': 'network diagnostics only; not AI inference benchmark', 'profile': profile,
                    'parallel_tcp_connections': 8, 'duration_s': 5, 'omit_s': 1,
                    'sum_received_mbps': throughput, 'clients': results, 'servers': server_results,
                    'before_counters': before, 'after_counters': after,
                    'firewall': self.host('fw', ['iptables', '-nvxL', 'FORWARD']),
                    'cpu_stat': command(['cat', '/proc/stat']).stdout}
        self.save(f'capacity-{profile.lower()}.json', evidence)
        self.assert_case('iperf-'+profile, all(r.get('success') for r in results+server_results) and throughput > 0, throughput)
        if profile == 'B':
            # The measured 40 Mbps floor is a diagnostic acceptance threshold below
            # the configured 50 Mbps aggregate fabric capacity, not a claimed result.
            self.assert_case('edge-supports-dual-path-load', throughput > 40, throughput)

    def negative(self):
        self.apply('A')
        before = {s: flow_signature(d) for s, d in self.flows().items()}
        ignore = self.ctl('apply', profile='B', decision='ignore', confirmed=False, actor='ignore-test')
        unconfirmed = self.ctl('apply', profile='B', decision='apply', confirmed=False)
        invalid = self.ctl('apply', profile='INVALID', decision='apply', confirmed=True)
        after = {s: flow_signature(d) for s, d in self.flows().items()}
        self.assert_case('ignore-unconfirmed-invalid-do-not-change-flows',
                         ignore.get('success') and not unconfirmed.get('success') and not invalid.get('success') and before == after)
        self.save('rejected-actions.json', {'ignore': ignore, 'unconfirmed': unconfirmed, 'invalid': invalid})
        try:
            command(['ip', 'link', 'set', 'leaf1-eth3', 'down'])
            failure = self.ctl('apply', profile='B', decision='apply', confirmed=True, actor='broken-path-test')
            self.save('negative-apply.json', failure)
            self.assert_case('broken-spine2-apply-fails-and-restores-a',
                             not failure.get('success') and failure.get('rollback_ok') and failure.get('new_profile') == 'A')
        finally:
            command(['ip', 'link', 'set', 'leaf1-eth3', 'up'])
        self.assert_case('restored-network-verifies', self.ctl('verify').get('success'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', default='acceptance')
    parser.add_argument('--quick', action='store_true', help='Connectivity and lifecycle only, for clean-clone check')
    args = parser.parse_args()
    if os.geteuid() != 0 or sys.platform != 'linux':
        parser.error('Run with sudo /usr/bin/python3 inside Ubuntu VM')
    if SOCKET.exists():
        parser.error('A testbed is already running; inspect and stop it before verification')
    if not args.label.replace('-', '').replace('_', '').isalnum():
        parser.error('Use letters, digits, underscore or hyphen for the label')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = ROOT/'evidence/network'/f'{stamp}-{args.label}'
    out.mkdir(parents=True)
    check = Check(out)
    result = {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'success': False,
              'label': args.label, 'quick': args.quick}
    try:
        sources = sorted(p for folder in ('topology', 'control', 'scripts', 'tests') for p in (ROOT/folder).rglob('*')
                         if p.is_file() and p.suffix in ('.py', '.json', '.sh') and not p.name.startswith('._'))
        check.save('source-manifest.json', {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
        environment = {'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                       'os_release': Path('/etc/os-release').read_text(),
                       'uname': command(['uname', '-a']).stdout,
                       'packages': command(['dpkg-query', '-W', '-f=${Package}\t${Version}\t${Architecture}\n',
                                            'mininet', 'openvswitch-switch', 'python3', 'iperf3', 'iptables', 'tcpdump']).stdout,
                       'base_commit': command(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], check=False).stdout.strip() or None,
                       'git_status': command(['git', '-C', str(ROOT), 'status', '--short'], check=False).stdout,
                       'source_identity': 'Use source-manifest.json; .git is optional for an archive deployment',
                       'config_hashes': {p: config_hash(p) for p in ('A', 'B')}}
        check.save('environment.json', environment)
        started = check.start('A')
        result['session_id'] = started['session_id']
        check.save('start.json', started)
        check.save('initial-verification.json', check.ctl('verify'))
        check.assert_case('initial-zero-loss-and-exact-rules', json.loads((out/'initial-verification.json').read_text())['success'])
        check.save('network-state.json', check.ctl('status'))
        failed_command = check.host('c1', ['/bin/sh', '-c', 'exit 7'])
        check.save('command-failure.json', failed_command)
        check.assert_case('exec-preserves-failure-exit-code', failed_command.get('returncode') == 7 and not failed_command.get('success'))
        for host in HOSTS:
            check.save(f'{host}-network.json', {cmd: check.host(host, argv) for cmd, argv in [
                ('addresses', ['ip', '-j', 'addr']), ('routes', ['ip', '-j', 'route']),
                ('neighbors', ['ip', '-j', 'neigh'])]})
        tc = {}
        shaping_ok = True
        for a, b, pa, pb, rate, *_ in LINKS:
            for node, port in ((a, pa), (b, pb)):
                intf = f'{node}-eth{port}'
                tc[intf] = {}
                for kind in ('class', 'qdisc'):
                    argv = ['tc', '-s', kind, 'show', 'dev', intf]
                    tc[intf][kind] = check.host(node, argv)['stdout'] if node in HOSTS else command(argv).stdout
                shaping_ok = shaping_ok and f'rate {rate}Mbit' in tc[intf]['class']
        check.save('tc.json', tc)
        check.assert_case('all-20-interface-shapers-have-declared-rates', shaping_ok)
        if not args.quick:
            for repeat in range(1, 4):
                for profile in ('A', 'B'):
                    check.save(f'apply-{profile.lower()}-{repeat}.json', check.apply(profile))
                    check.path_probe(profile, repeat)
            check.firewall()
            check.capacity('A')
            check.capacity('B')
            check.negative()
        cleanup = check.ctl('stop')
        check.save('cleanup.json', cleanup)
        check.assert_case('cleanup-removes-owned-resources', cleanup.get('success'))
        for i in range(2):
            check.start('A' if i == 0 else 'B')
            check.assert_case(f'lifecycle-{i+1}', check.ctl('verify').get('success'))
            check.assert_case(f'lifecycle-cleanup-{i+1}', check.ctl('stop').get('success'))
        result['success'] = True
    except Exception as error:
        result['error'] = str(error)
        print(f'FAIL {error}', flush=True)
    finally:
        if SOCKET.exists():
            try:
                check.save('final-cleanup.json', check.ctl('stop'))
            except Exception as error:
                result['cleanup_error'] = str(error)
                result['success'] = False
        if Path('/run/nhom18/apply.jsonl').exists():
            events = [json.loads(line) for line in Path('/run/nhom18/apply.jsonl').read_text().splitlines() if line.strip()]
            (out/'apply-events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events
                                                       if e.get('session_id') == result.get('session_id')))
        result['cases'] = check.cases
        result['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        check.save('result.json', result)
        (out/'exit-code.txt').write_text('0\n' if result['success'] else '1\n')
        if 'SUDO_UID' in os.environ:
            for p in [*out.rglob('*'), out]:
                os.chown(p, int(os.environ['SUDO_UID']), int(os.environ['SUDO_GID']))
        check.pool.shutdown(wait=True)
        print('EVIDENCE '+str(out), flush=True)
    return 0 if result['success'] else 1


if __name__ == '__main__':
    sys.exit(main())
