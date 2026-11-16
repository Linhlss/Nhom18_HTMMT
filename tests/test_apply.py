"""Exercise approval and rollback paths without requiring a running Mininet."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock

from topology.model import SWITCHES, flow_rules
from topology.runtime import Network


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.net = Network(self.temp.name)
        self.net.profile = 'A'
        self.net.dumps = lambda: {s: '\n'.join(flow_rules(self.net.profile)[s]) for s in SWITCHES}
        self.net.install = Mock()
        self.net.verify = Mock(return_value={'success': True})
        self.net.save_state = Mock()

    def tearDown(self):
        self.temp.cleanup()

    def test_unconfirmed_and_invalid_do_not_apply(self):
        for profile, decision, confirm in [('B', 'apply', False), ('C', 'apply', True), ('B', 'unknown', True)]:
            with self.assertRaises(ValueError):
                self.net.apply(profile, decision, confirm, 'test')
        self.net.install.assert_not_called()
        self.assertEqual(self.net.profile, 'A')

    def test_ignore_preserves_a(self):
        result = self.net.apply('B', 'ignore', False, 'test')
        self.assertTrue(result['success'])
        self.assertTrue(result['unchanged'])
        self.assertEqual(result['new_profile'], 'A')
        self.net.install.assert_not_called()

    def test_busy_rejected_before_any_install(self):
        self.net.active_commands = 1
        with self.assertRaises(RuntimeError):
            self.net.apply('B', 'apply', True, 'test')
        self.net.install.assert_not_called()

    def test_failed_verification_rolls_back_and_still_fails(self):
        self.net.verify.side_effect = [{'success': False}, {'success': True}]
        result = self.net.apply('B', 'apply', True, 'test')
        self.assertFalse(result['success'])
        self.assertTrue(result['rollback_ok'])
        self.assertEqual(result['new_profile'], 'A')
        self.assertEqual([c.args[0] for c in self.net.install.call_args_list], ['B', 'A'])

    def test_failed_rollback_marks_unknown_not_success(self):
        self.net.install.side_effect = [RuntimeError('injected install failure'), RuntimeError('injected restore failure')]
        # A dump is still possible although the effective profile is unknown.
        self.net.dumps = lambda: {'leaf1': 'unknown state'}
        result = self.net.apply('B', 'apply', True, 'test')
        self.assertFalse(result['success'])
        self.assertFalse(result['rollback_ok'])
        self.assertIsNone(result['new_profile'])

    def test_repeated_apply_is_verified_and_logged(self):
        for _ in range(2):
            self.assertTrue(self.net.apply('B', 'apply', True, 'test')['success'])
        self.assertEqual(self.net.profile, 'B')
        self.assertEqual(self.net.verify.call_count, 2)
        self.assertEqual(len((Path(self.temp.name)/'apply.jsonl').read_text().splitlines()), 2)


if __name__ == '__main__':
    unittest.main()
