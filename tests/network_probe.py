#!/usr/bin/python3
"""Short TCP connectivity fixture, not the AI inference workload owned by TV2."""
import argparse
import selectors
import socket
import sys
import time


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='action', required=True)
    server = sub.add_parser('server')
    server.add_argument('--duration', type=float, default=8)
    client = sub.add_parser('client')
    client.add_argument('address')
    client.add_argument('port', type=int)
    args = p.parse_args()
    if args.action == 'client':
        try:
            with socket.create_connection((args.address, args.port), timeout=1.5) as sock:
                message = sock.recv(100)
                if message != b'nhom18-network-probe':
                    return 1
                print(message.decode())
                return 0
        except OSError as error:
            print(str(error), file=sys.stderr)
            return 1
    with selectors.DefaultSelector() as selector:
        listeners = []
        try:
            for port in (8000, 9000):
                listener = socket.socket()
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind(('0.0.0.0', port))
                listener.listen(16)
                listeners.append(listener)
                selector.register(listener, selectors.EVENT_READ)
            print('LISTENING 8000 9000', flush=True)
            until = time.monotonic() + args.duration
            while time.monotonic() < until:
                for key, _ in selector.select(timeout=0.1):
                    sock, _ = key.fileobj.accept()
                    with sock:
                        sock.sendall(b'nhom18-network-probe')
        finally:
            for listener in listeners:
                listener.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
