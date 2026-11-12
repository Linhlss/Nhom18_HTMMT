#!/usr/bin/python3
"""Exercise two real Mininet hosts and verify forwarding plus cleanup."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def command(args):
    return subprocess.run(args, text=True, capture_output=True, timeout=15)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--negative-control', action='store_true',
                        help='Intentionally disconnect h1; this run MUST exit nonzero.')
    args = parser.parse_args()
    result = {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'negative_control': args.negative_control, 'success': False,
              'cleanup_ok': False, 'pings': []}
    net = None
    owned_topology = False
    try:
        if os.geteuid() != 0:
            raise RuntimeError('Root is required for Linux network namespaces.')
        from mininet.net import Mininet
        from mininet.node import OVSBridge
        from mininet.log import setLogLevel
        setLogLevel('info')
        bridges = command(['ovs-vsctl', '--timeout=10', 'list-br']).stdout.split()
        if 's1' in bridges or command(['ip', 'link', 'show', 's1-eth1']).returncode == 0:
            raise RuntimeError('s1/s1-eth1 already exists; stop that testbed before running this check.')
        net = Mininet(controller=None, switch=OVSBridge, build=False)
        owned_topology = True
        h1 = net.addHost('h1', ip='10.0.0.1/24')
        h2 = net.addHost('h2', ip='10.0.0.2/24')
        s1 = net.addSwitch('s1')
        net.addLink(h1, s1)
        net.addLink(h2, s1)
        net.build()
        net.start()
        result['hosts'] = [h.name for h in net.hosts]
        result['switches'] = [s.name for s in net.switches]
        result['links'] = [str(link) for link in net.links]
        ports = command(['ovs-vsctl', '--timeout=10', 'list-ports', 's1'])
        result['ovs_ports'] = sorted(ports.stdout.split())
        print('TOPOLOGY', json.dumps({k: result[k] for k in ['hosts', 'switches', 'links', 'ovs_ports']}), flush=True)
        if len(net.hosts) != 2 or len(net.switches) != 1 or len(net.links) != 2:
            raise RuntimeError('Expected exactly two hosts, one switch, and two links.')
        if ports.returncode != 0 or result['ovs_ports'] != ['s1-eth1', 's1-eth2']:
            raise RuntimeError('The two OVS bridge ports were not created correctly.')
        if args.negative_control:
            net.configLinkStatus('h1', 's1', 'down')
            print('NEGATIVE CONTROL: h1-s1 is intentionally down.', flush=True)
        result['pingall_loss_percent'] = net.pingAll(timeout='2')
        for source, destination in [(h1, h2), (h2, h1)]:
            proc = source.popen(['ping', '-n', '-c', '5', '-W', '2', destination.IP()],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            try:
                output, _ = proc.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                raise RuntimeError(f'Ping timed out: {source.name} -> {destination.name}')
            print(f'PING {source.name} -> {destination.name}\n{output}', flush=True)
            match = re.search(r'(\d+) packets transmitted, (\d+) received,.*?([\d.]+)% packet loss', output)
            ping = {'source': source.name, 'destination': destination.name,
                    'exit_code': proc.returncode, 'parsed': match is not None}
            if match:
                ping.update(sent=int(match[1]), received=int(match[2]), loss_percent=float(match[3]))
            result['pings'].append(ping)
        result['success'] = result['pingall_loss_percent'] == 0 and all(
            p['parsed'] and p['exit_code'] == 0 and p['sent'] == p['received'] == 5
            and p['loss_percent'] == 0 for p in result['pings'])
        if not result['success']:
            result['error'] = 'Connectivity check failed; see the raw ping output.'
    except Exception as error:
        result['error'] = str(error)
        print(f'ERROR: {error}', file=sys.stderr, flush=True)
    finally:
        if net is not None:
            try:
                net.stop()
            except Exception as error:
                result['cleanup_error'] = str(error)
        if owned_topology:
            check = command(['ovs-vsctl', '--timeout=10', 'list-br'])
            result['remaining_test_interfaces'] = [name for name in ['s1', 's1-eth1', 's1-eth2']
                                                  if command(['ip', 'link', 'show', name]).returncode == 0]
            result['cleanup_ok'] = check.returncode == 0 and 's1' not in check.stdout.split() \
                and not result['remaining_test_interfaces'] and 'cleanup_error' not in result
        result['success'] = result['success'] and result['cleanup_ok']
        result['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print('RESULT', json.dumps(result), flush=True)
    return 0 if result['success'] else 1


if __name__ == '__main__':
    sys.exit(main())
