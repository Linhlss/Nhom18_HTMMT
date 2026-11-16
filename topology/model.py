"""Deterministic addresses, ports and forwarding rules, independent of Mininet."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COOKIE = '0x1818'
SWITCHES = ('leaf1', 'leaf2', 'spine1', 'spine2')
HOSTS = ('c1', 'c2', 'gw', 'fw', 'a1', 'a2')
ENDPOINTS = ('c1', 'c2', 'a1', 'a2')
IPS = {'c1': '10.18.1.10', 'c2': '10.18.2.10',
       'a1': '10.18.3.11', 'a2': '10.18.3.12'}
SUBNETS = {'c1': '10.18.1.0/24', 'c2': '10.18.2.0/24'}
ADDRESSES = {
    'c1': [('c1-eth0', '10.18.1.10/24')],
    'c2': [('c2-eth0', '10.18.2.10/24')],
    'gw': [('gw-eth0', '10.18.1.1/24'), ('gw-eth1', '10.18.2.1/24'),
           ('gw-eth2', '10.18.254.1/30')],
    'fw': [('fw-eth0', '10.18.254.2/30'), ('fw-eth1', '10.18.3.1/24')],
    'a1': [('a1-eth0', '10.18.3.11/24')],
    'a2': [('a2-eth0', '10.18.3.12/24')],
}
ROUTES = {'c1': ['default via 10.18.1.1'], 'c2': ['default via 10.18.2.1'],
          'gw': ['10.18.3.0/24 via 10.18.254.2'],
          'fw': ['10.18.1.0/24 via 10.18.254.1', '10.18.2.0/24 via 10.18.254.1'],
          'a1': ['default via 10.18.3.1'], 'a2': ['default via 10.18.3.1']}
# name1, name2, port1, port2, rate Mbps, delay, queue packets
LINKS = [
    ('c1', 'gw', 0, 0, 100, '0ms', 100),
    ('c2', 'gw', 0, 1, 100, '0ms', 100),
    ('gw', 'fw', 2, 0, 100, '0ms', 100),
    ('fw', 'leaf1', 1, 1, 100, '0ms', 100),
    ('leaf1', 'spine1', 2, 1, 25, '1ms', 100),
    ('leaf1', 'spine2', 3, 1, 25, '1ms', 100),
    ('spine1', 'leaf2', 2, 1, 25, '1ms', 100),
    ('spine2', 'leaf2', 2, 2, 25, '1ms', 100),
    ('leaf2', 'a1', 3, 0, 100, '0ms', 100),
    ('leaf2', 'a2', 4, 0, 100, '0ms', 100),
]


def profile_config(profile):
    if profile not in ('A', 'B'):
        raise ValueError('Only profiles A and B are allowed')
    data = json.loads((ROOT / 'topology/configs' / f'profile_{profile.lower()}.json').read_text())
    expected = {'c1': 'spine1', 'c2': 'spine1' if profile == 'A' else 'spine2'}
    if data.get('id') != profile or data.get('client_paths') != expected:
        raise ValueError('Preset differs from the verified forwarding design')
    return data


def flow_rules(profile):
    """Explicit IPv4 and ARP tree rules; no NORMAL/FLOOD across the cyclic fabric."""
    paths = profile_config(profile)['client_paths']
    rules = {s: [f'cookie={COOKIE},priority=0,actions=drop'] for s in SWITCHES}

    def add(switch, match, output, priority=100):
        rules[switch].append(f'cookie={COOKIE},priority={priority},{match},actions=output:{output}')

    for client, subnet in SUBNETS.items():
        path = paths[client]
        uplink = 2 if path == 'spine1' else 3
        downlink = 1 if path == 'spine1' else 2
        add('leaf1', f'in_port=1,ip,nw_src={subnet},nw_dst=10.18.3.0/24', uplink)
        # The reverse direction enters leaf2 at a server port.
        for server_port in (3, 4):
            add('leaf2', f'in_port={server_port},ip,nw_dst={subnet}', downlink)
        add('leaf1', f'in_port={uplink},ip,nw_dst={subnet}', 1)
    # Server destination selection, including same-leaf a1 <-> a2 traffic.
    for port, server in [(3, 'a1'), (4, 'a2')]:
        for ingress in (1, 2, 3, 4):
            if ingress != port:
                add('leaf2', f'in_port={ingress},ip,nw_dst={IPS[server]}', port, 110)
    # Probes to the firewall's fabric address use spine1 in both profiles.
    for ingress in (3, 4):
        add('leaf2', f'in_port={ingress},ip,nw_dst=10.18.3.1', 1, 110)
    add('leaf1', 'in_port=2,ip,nw_dst=10.18.3.1', 1, 110)
    for spine in ('spine1', 'spine2'):
        add(spine, 'in_port=1,ip', 2)
        add(spine, 'in_port=2,ip', 1)
    # ARP tree is always fw - leaf1 - spine1 - leaf2 - a1/a2.
    add('leaf1', 'in_port=1,arp', 2)
    add('leaf1', 'in_port=2,arp', 1)
    add('spine1', 'in_port=1,arp', 2)
    add('spine1', 'in_port=2,arp', 1)
    for ingress, outputs in ((1, '3,output:4'), (3, '1,output:4'), (4, '1,output:3')):
        add('leaf2', f'in_port={ingress},arp', outputs)
    return rules


def config_hash(profile):
    payload = {'addresses': ADDRESSES, 'routes': ROUTES, 'links': LINKS,
               'profile': profile_config(profile), 'flows': flow_rules(profile),
               'firewall_tcp_ports': [8000, '5201:5208']}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def flow_signature(dump):
    """Ignore counters/durations when comparing effective OpenFlow configuration."""
    signatures = []
    for line in dump.splitlines():
        if 'actions=' not in line:
            continue
        match, actions = line.strip().split('actions=', 1)
        fields = []
        for token in match.replace(' ', '').strip(',').split(','):
            key = token.split('=', 1)[0]
            if key in ('duration', 'n_packets', 'n_bytes', 'idle_age', 'hard_age') or token == 'table=0':
                continue
            if token:
                fields.append(token)
        signatures.append(','.join(sorted(fields)) + ' actions=' + actions.replace(' ', ''))
    return sorted(signatures)
