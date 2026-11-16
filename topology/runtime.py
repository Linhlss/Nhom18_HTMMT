"""Linux-only Mininet lifecycle and operator-approved profile transactions."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import threading
import time

from topology.model import (ADDRESSES, ENDPOINTS, HOSTS, IPS, LINKS, ROOT,
                            ROUTES, SWITCHES, config_hash, flow_rules, flow_signature)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def run(argv, check=True, timeout=15):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f'{argv!r}: exit {p.returncode}: {p.stderr.strip()} {p.stdout.strip()}')
    return p


class Network:
    def __init__(self, runtime_dir):
        self.directory = Path(runtime_dir)
        self.net = None
        self.profile = None
        self.lock = threading.RLock()
        self.active_commands = 0
        self.procs = set()
        self.proc_lock = threading.Lock()
        self.session_id = os.urandom(8).hex()
        self.created = utc()
        self.owns = False

    def host_run(self, host, argv, timeout=15):
        if host not in HOSTS:
            raise ValueError('Unknown host')
        node = self.net[host]
        # Python creates the process group. Do not also ask mnexec -d to detach:
        # a second setsid can fork and lose the actual command's failure status.
        p = node.popen(argv, mncmd=['mnexec', '-a', str(node.pid)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, start_new_session=True, cwd=str(ROOT))
        with self.proc_lock:
            self.procs.add(p)
        try:
            out, err = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            out, err = p.communicate()
            raise RuntimeError(f'Command timed out on {host}: {argv!r}')
        finally:
            with self.proc_lock:
                self.procs.discard(p)
        return {'returncode': p.returncode, 'stdout': out[-2_000_000:], 'stderr': err[-2_000_000:]}

    def host_checked(self, host, argv):
        result = self.host_run(host, argv)
        if result['returncode']:
            raise RuntimeError(f'{host}: {argv!r}: {result}')
        return result['stdout']

    def start(self, profile):
        from mininet.net import Mininet
        from mininet.node import OVSSwitch
        from mininet.link import TCLink
        from mininet.log import setLogLevel
        setLogLevel('warning')
        # A collision is an error: never invoke global mn -c on another testbed.
        bridges = run(['ovs-vsctl', '--timeout=10', 'list-br']).stdout.split()
        if any(s in bridges for s in SWITCHES):
            raise RuntimeError('A project bridge already exists; inspect its owner before starting')
        for left, right, lp, rp, *_ in LINKS:
            for name in (f'{left}-eth{lp}', f'{right}-eth{rp}'):
                if run(['ip', 'link', 'show', name], check=False).returncode == 0:
                    raise RuntimeError(f'Interface collision: {name}')
        self.net = Mininet(controller=None, switch=OVSSwitch, link=TCLink, build=False,
                           autoSetMacs=False)
        self.owns = True
        for i, name in enumerate(HOSTS, 1):
            self.net.addHost(name, ip=None, mac=f'02:18:00:00:00:{i:02x}')
        for i, name in enumerate(SWITCHES, 1):
            self.net.addSwitch(name, dpid=f'{i:016x}', protocols='OpenFlow13',
                               failMode='secure', inband=False)
        for left, right, lp, rp, bw, delay, queue in LINKS:
            self.net.addLink(left, right, port1=lp, port2=rp, bw=bw, delay=delay,
                             max_queue_size=queue, use_htb=True)
        self.net.build()
        self.net.start()
        for host, addresses in ADDRESSES.items():
            for intf, ip in addresses:
                self.host_checked(host, ['ip', 'addr', 'flush', 'dev', intf])
                self.host_checked(host, ['ip', 'addr', 'add', ip, 'dev', intf])
                self.host_checked(host, ['ip', 'link', 'set', intf, 'up'])
            for route in ROUTES[host]:
                self.host_checked(host, ['ip', 'route', 'replace', *route.split()])
        for host in ('gw', 'fw'):
            self.host_checked(host, ['sysctl', '-qw', 'net.ipv4.ip_forward=1'])
        self.configure_firewall()
        self.install(profile)
        self.profile = profile
        verification = self.verify()
        if not verification['success']:
            raise RuntimeError(f'Start verification failed: {verification}')
        self.save_state()

    def configure_firewall(self):
        commands = [
            ['iptables', '-P', 'FORWARD', 'DROP'],
            ['iptables', '-F', 'FORWARD'],
            ['iptables', '-A', 'FORWARD', '-m', 'conntrack', '--ctstate', 'INVALID', '-j', 'DROP'],
            ['iptables', '-A', 'FORWARD', '-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'],
        ]
        for subnet in ('10.18.1.0/24', '10.18.2.0/24'):
            commands += [
                ['iptables', '-A', 'FORWARD', '-s', subnet, '-d', '10.18.3.0/24', '-p', 'icmp', '-j', 'ACCEPT'],
                ['iptables', '-A', 'FORWARD', '-s', '10.18.3.0/24', '-d', subnet, '-p', 'icmp', '-j', 'ACCEPT'],
                ['iptables', '-A', 'FORWARD', '-s', subnet, '-d', '10.18.3.0/24', '-p', 'tcp',
                 '-m', 'multiport', '--dports', '8000,5201:5208', '-m', 'conntrack', '--ctstate', 'NEW', '-j', 'ACCEPT'],
            ]
        commands.append(['iptables', '-A', 'FORWARD', '-j', 'DROP'])
        for command in commands:
            self.host_checked('fw', command)

    def dumps(self):
        return {s: run(['ovs-ofctl', '-O', 'OpenFlow13', 'dump-flows', s]).stdout for s in SWITCHES}

    def install(self, profile):
        rules = flow_rules(profile)
        for switch in SWITCHES:
            with tempfile.NamedTemporaryFile(mode='w', prefix='n18-flows-', delete=False) as f:
                f.write('\n'.join(rules[switch]) + '\n')
                filename = f.name
            try:
                run(['ovs-ofctl', '-O', 'OpenFlow13', 'replace-flows', switch, filename])
            finally:
                Path(filename).unlink(missing_ok=True)

    def status(self):
        ports = {}
        for switch in SWITCHES:
            ports[switch] = run(['ovs-ofctl', '-O', 'OpenFlow13', 'show', switch]).stdout
        return {'success': True, 'session_id': self.session_id, 'created_utc': self.created,
                'profile': self.profile, 'config_hash': config_hash(self.profile) if self.profile else None,
                'hosts': list(HOSTS), 'switches': list(SWITCHES), 'endpoints': IPS,
                'addresses': ADDRESSES, 'routes': ROUTES, 'links': LINKS, 'ports': ports,
                'active_commands': self.active_commands}

    def save_state(self):
        temp = self.directory / 'state.tmp'
        temp.write_text(json.dumps(self.status(), indent=2) + '\n')
        temp.replace(self.directory / 'state.json')

    def verify(self):
        checks = []
        # Deliberate explicit pairs: switches have no IP and firewall policy is directional.
        for left in ('c1', 'c2'):
            for right in ('a1', 'a2'):
                for source, destination in ((left, right), (right, left)):
                    self.host_run(source, ['ping', '-n', '-c', '1', '-W', '2', IPS[destination]])
                    p = self.host_run(source, ['ping', '-n', '-c', '3', '-i', '0.1', '-W', '2', IPS[destination]])
                    match = re.search(r'(\d+) packets transmitted, (\d+) received,.*?([\d.]+)% packet loss', p['stdout'])
                    checks.append({'source': source, 'destination': destination, **p,
                                   'success': p['returncode'] == 0 and bool(match)
                                   and match[1] == match[2] == '3' and float(match[3]) == 0})
        flow_dump = self.dumps()
        # Verify expected rules, not just connectivity or the in-memory profile label.
        rules_ok = all(flow_signature(flow_dump[s]) == flow_signature('\n'.join(flow_rules(self.profile)[s]))
                       for s in SWITCHES)
        inventory_ok = (len(self.net.hosts) == 6 and len(self.net.switches) == 4 and len(self.net.links) == 10)
        return {'success': rules_ok and inventory_ok and all(c['success'] for c in checks),
                'profile': self.profile, 'rules_ok': rules_ok, 'inventory_ok': inventory_ok,
                'pings': checks, 'flows': flow_dump}

    def apply(self, profile, decision, confirm, actor):
        # Validate before any command that can change the datapath.
        config_hash(profile)
        if decision not in ('apply', 'ignore'):
            raise ValueError('decision must be apply or ignore')
        if decision == 'apply' and confirm is not True:
            raise ValueError('Apply requires explicit --confirm / confirmed=true')
        if decision == 'apply' and self.active_commands:
            raise RuntimeError('Stop workload commands before changing profile; rerun at the same load afterwards')
        before = self.dumps()
        old = self.profile
        event = {'timestamp_utc': utc(), 'session_id': self.session_id, 'actor': actor,
                 'decision': decision, 'confirmed': confirm, 'old_profile': old,
                 'requested_profile': profile, 'old_config_hash': config_hash(old),
                 'requested_config_hash': config_hash(profile), 'success': False}
        try:
            if decision == 'ignore':
                after = self.dumps()
                event['success'] = all(flow_signature(before[s]) == flow_signature(after[s]) for s in SWITCHES)
                event['unchanged'] = event['success']
            else:
                self.install(profile)
                self.profile = profile
                verification = self.verify()
                event['verification'] = verification
                if not verification['success']:
                    raise RuntimeError('Post-apply forwarding verification failed')
                event['success'] = True
            event['new_profile'] = self.profile
        except Exception as error:
            event['error'] = str(error)
            if decision == 'apply':
                try:
                    self.install(old)
                    self.profile = old
                    restored = self.verify()
                    event['rollback_ok'] = restored['success']
                    if not restored['success']:
                        self.profile = None
                except Exception as rollback_error:
                    self.profile = None
                    event['rollback_ok'] = False
                    event['rollback_error'] = str(rollback_error)
            event['new_profile'] = self.profile
        event['finished_utc'] = utc()
        event['after_flows'] = self.dumps()
        with (self.directory / 'apply.jsonl').open('a') as f:
            f.write(json.dumps(event) + '\n')
        self.save_state()
        return event

    def stop(self):
        with self.proc_lock:
            for p in list(self.procs):
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        if self.net is not None and self.owns:
            self.net.stop()
            self.net = None
        leftovers = [s for s in SWITCHES if s in run(['ovs-vsctl', 'list-br']).stdout.split()]
        interfaces = []
        for left, right, lp, rp, *_ in LINKS:
            for name in (f'{left}-eth{lp}', f'{right}-eth{rp}'):
                if run(['ip', 'link', 'show', name], check=False).returncode == 0:
                    interfaces.append(name)
        return {'success': not leftovers and not interfaces, 'remaining_bridges': leftovers,
                'remaining_interfaces': interfaces}
