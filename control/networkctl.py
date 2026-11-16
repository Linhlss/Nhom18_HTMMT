#!/usr/bin/python3
"""Root-only local CLI/JSON interface. Run from any directory inside Ubuntu VM."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from topology.model import ENDPOINTS, HOSTS, config_hash

RUNTIME = Path('/run/nhom18')
SOCKET = RUNTIME / 'network.sock'


def request(payload, timeout=30):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(str(SOCKET))
        s.sendall(json.dumps(payload).encode() + b'\n')
        chunks = []
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            if chunk.endswith(b'\n'):
                break
        result = json.loads(b''.join(chunks))
    if payload.get('action') == 'stop':
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if not SOCKET.exists():
                with (RUNTIME / 'owner.lock').open('a') as lock:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        fcntl.flock(lock, fcntl.LOCK_UN)
                        return result
                    except BlockingIOError:
                        pass
            time.sleep(0.05)
        raise RuntimeError('Shutdown did not finish; inspect runtime before starting again')
    return result


def serve(profile):
    from topology.runtime import Network
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    os.chmod(RUNTIME, 0o700)
    with (RUNTIME / 'owner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        SOCKET.unlink(missing_ok=True)
        network = Network(RUNTIME)
        server = None

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                try:
                    data = json.loads(self.rfile.readline(1_000_001))
                    action = data.get('action')
                    if action == 'exec':
                        host, argv = data.get('host'), data.get('argv')
                        timeout = data.get('timeout', 30)
                        if host not in HOSTS or not isinstance(argv, list) or not argv \
                           or not all(isinstance(v, str) and '\x00' not in v for v in argv) \
                           or not isinstance(timeout, (int, float)) or not 0 < timeout <= 600:
                            raise ValueError('Invalid host, argv or timeout (1..600 seconds)')
                        with network.lock:
                            network.active_commands += 1
                        try:
                            result = network.host_run(host, argv, timeout)
                            result['success'] = result['returncode'] == 0
                        finally:
                            with network.lock:
                                network.active_commands -= 1
                    else:
                        with network.lock:
                            if action == 'status':
                                result = network.status()
                            elif action == 'verify':
                                if network.active_commands:
                                    raise RuntimeError('Stop workload commands before verification')
                                result = network.verify()
                            elif action == 'apply':
                                if network.active_commands:
                                    raise RuntimeError('Stop workload commands before changing profile')
                                result = network.apply(data.get('profile'), data.get('decision'),
                                                       data.get('confirmed'), data.get('actor', 'operator'))
                            elif action == 'stop':
                                result = network.stop()
                                threading.Thread(target=self.server.shutdown, daemon=True).start()
                            else:
                                raise ValueError('Unknown action')
                except Exception as error:
                    result = {'success': False, 'error': str(error)}
                self.wfile.write(json.dumps(result).encode() + b'\n')

        class Server(socketserver.ThreadingUnixStreamServer):
            daemon_threads = True

        def shutdown(signum, frame):
            if server is not None:
                threading.Thread(target=server.shutdown, daemon=True).start()

        try:
            network.start(profile)
            server = Server(str(SOCKET), Handler)
            os.chmod(SOCKET, 0o600)
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, shutdown)
            server.serve_forever(poll_interval=0.2)
        finally:
            cleanup = network.stop() if network.owns else {'success': True}
            (RUNTIME / 'last-cleanup.json').write_text(json.dumps(cleanup, indent=2) + '\n')
            if server:
                server.server_close()
            SOCKET.unlink(missing_ok=True)
            (RUNTIME / 'state.json').unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    start = sub.add_parser('start')
    start.add_argument('--profile', choices=['A', 'B'], default='A')
    internal = sub.add_parser('_serve', help=argparse.SUPPRESS)
    internal.add_argument('--profile', choices=['A', 'B'], required=True)
    for action in ('status', 'verify', 'stop'):
        sub.add_parser(action)
    execute = sub.add_parser('exec')
    execute.add_argument('--timeout', type=float, default=30)
    execute.add_argument('host', choices=HOSTS)
    execute.add_argument('argv', nargs=argparse.REMAINDER)
    apply = sub.add_parser('apply')
    apply.add_argument('--profile', choices=['A', 'B'], required=True)
    apply.add_argument('--decision', choices=['apply', 'ignore'], required=True)
    apply.add_argument('--confirm', action='store_true')
    apply.add_argument('--actor', default='operator')
    args = parser.parse_args()
    try:
        if os.geteuid() != 0 or sys.platform != 'linux':
            raise RuntimeError('Run with sudo /usr/bin/python3 inside the Ubuntu VM')
        if args.action == '_serve':
            serve(args.profile)
            return 0
        if args.action == 'start':
            config_hash(args.profile)
            if SOCKET.exists():
                raise RuntimeError('A runtime socket already exists; inspect status before starting')
            logs = ROOT / '.local/runtime'
            logs.mkdir(parents=True, exist_ok=True)
            with (logs / 'network.log').open('a') as log:
                daemon = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '_serve',
                                           '--profile', args.profile], stdout=log, stderr=log,
                                          cwd=ROOT, start_new_session=True)
            deadline = time.monotonic() + 50
            while time.monotonic() < deadline:
                if SOCKET.exists():
                    result = request({'action': 'status'})
                    print(json.dumps(result))
                    return 0 if result['success'] else 1
                if daemon.poll() is not None:
                    raise RuntimeError(f'Start failed; see {logs / "network.log"}')
                time.sleep(0.2)
            daemon.terminate()
            daemon.wait(timeout=15)
            raise RuntimeError('Start timed out; see .local/runtime/network.log')
        payload = {'action': args.action}
        if args.action == 'exec':
            argv = args.argv[1:] if args.argv[:1] == ['--'] else args.argv
            if not argv:
                raise ValueError('exec requires a command after the host name')
            payload.update(host=args.host, argv=argv, timeout=args.timeout)
        elif args.action == 'apply':
            payload.update(profile=args.profile, decision=args.decision,
                           confirmed=args.confirm, actor=args.actor)
        result = request(payload, timeout=args.timeout + 10 if args.action == 'exec' else 60)
        print(json.dumps(result, ensure_ascii=False))
        if args.action == 'stop':
            deadline = time.monotonic() + 5
            while SOCKET.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
        return 0 if result.get('success') else 1
    except Exception as error:
        print(json.dumps({'success': False, 'error': str(error)}), file=sys.stdout)
        return 1


if __name__ == '__main__':
    sys.exit(main())
