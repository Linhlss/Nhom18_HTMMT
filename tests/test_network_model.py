"""Test invariants that prevent loops, asymmetric paths and false verification."""
import unittest
from topology.model import HOSTS, IPS, LINKS, SWITCHES, config_hash, flow_rules, flow_signature


class ModelTests(unittest.TestCase):
    def test_topology_connected_and_exact_size(self):
        nodes = set(HOSTS) | set(SWITCHES)
        self.assertEqual(len(nodes), 10)
        self.assertEqual(len(LINKS), 10)
        seen, pending = set(), ['c1']
        ports = set()
        for a, b, pa, pb, rate, *_ in LINKS:
            for endpoint in [(a, pa), (b, pb)]:
                self.assertNotIn(endpoint, ports)
                ports.add(endpoint)
            self.assertEqual(rate, 25 if a in SWITCHES and b in SWITCHES else 100)
        while pending:
            n = pending.pop()
            if n in seen:
                continue
            seen.add(n)
            pending += [b if a == n else a for a, b, *_ in LINKS if a == n or b == n]
        self.assertEqual(seen, nodes)

    def test_profile_paths_and_arp_are_deterministic(self):
        a, b = flow_rules('A'), flow_rules('B')
        self.assertEqual(a['spine1'], b['spine1'])
        self.assertEqual(a['spine2'], b['spine2'])
        for profile, rules in [('A', a), ('B', b)]:
            text = '\n'.join(sum(rules.values(), []))
            self.assertNotIn('NORMAL', text.upper())
            self.assertNotIn('FLOOD', text.upper())
            self.assertFalse(any(',arp,' in r for r in rules['spine2']))
            for subnet, uplink, downlink in [('10.18.1.0/24', 2, 1),
                                             ('10.18.2.0/24', 2 if profile == 'A' else 3,
                                              1 if profile == 'A' else 2)]:
                self.assertTrue(any(f'nw_src={subnet},nw_dst=10.18.3.0/24,actions=output:{uplink}' in r for r in rules['leaf1']))
                self.assertTrue(any(f'in_port={uplink},ip,nw_dst={subnet},actions=output:1' in r for r in rules['leaf1']))
                for ingress in (3, 4):
                    self.assertTrue(any(f'in_port={ingress},ip,nw_dst={subnet},actions=output:{downlink}' in r for r in rules['leaf2']))
        self.assertNotEqual(config_hash('A'), config_hash('B'))
        self.assertEqual(config_hash('A'), config_hash('A'))

    def test_counter_changes_do_not_hide_rule_changes(self):
        expected = 'cookie=0x1818,priority=100,in_port=1,ip,nw_dst=10.18.3.11,actions=output:2'
        actual = ' cookie=0x1818, duration=2.14s, table=0, n_packets=7, n_bytes=800, priority=100,ip,in_port=1,nw_dst=10.18.3.11 actions=output:2'
        self.assertEqual(flow_signature(expected), flow_signature(actual))
        self.assertNotEqual(flow_signature(expected), flow_signature(actual.replace('output:2', 'output:3')))
        self.assertNotEqual(flow_signature(expected), flow_signature(actual.replace('nw_dst=10.18.3.11', 'nw_dst=10.18.3.12')))

    def test_invalid_profile_rejected(self):
        for invalid in ['C', '../../etc/passwd', None, 'a']:
            with self.assertRaises(ValueError):
                flow_rules(invalid)


if __name__ == '__main__':
    unittest.main()
