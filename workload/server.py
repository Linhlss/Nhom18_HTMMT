#!/usr/bin/python3
"""AI-inference server emulator for protocol tcp-binary-v1 (TV2, docs/workload-spec.md).

It does not run any model: it waits service_delay_ms (requested by the client), then returns a
response frame of exactly resp_size_bytes. Each connection is served FIFO: a reader thread
timestamps requests as soon as they are fully read; a worker thread serves them in order.

Exit code: 0 when --expect-requests valid requests were served without protocol errors;
1 otherwise (timeout, invalid request, framing error). --fault is for negative controls only.
"""
import argparse
import datetime
import json
from pathlib import Path
import queue
import selectors
import socket
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workload import framing  # noqa: E402
from workload.protocol import (STATUS_INVALID_REQ, STATUS_OK, min_response_bytes,  # noqa: E402
                               response_meta, validate_request)


def utc_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


class Server:
    def __init__(self, args):
        self.args = args
        self.out = Path(args.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.log_lock = threading.Lock()
        self.log = (self.out / 'server-events.jsonl').open('a', encoding='utf-8')
        self.stats_lock = threading.Lock()
        self.served = self.valid = self.invalid = self.protocol_errors = 0
        self.active = 0
        self.faults = 0

    def event(self, record):
        record.setdefault('utc', utc_iso())
        with self.log_lock:
            self.log.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')
            self.log.flush()

    def handle(self, conn, peer):
        work = queue.Queue()
        conn_info = {'client_ip': peer[0], 'client_port': peer[1]}
        self.event({'event': 'connection_open', **conn_info})

        def reader():
            try:
                while True:
                    meta, nbytes = framing.read_frame(conn)
                    work.put((meta, nbytes, time.monotonic_ns(), utc_iso()))
            except EOFError:
                pass
            except (framing.FrameError, ConnectionError, OSError) as error:
                with self.stats_lock:
                    self.protocol_errors += 1
                self.event({'event': 'protocol_error', 'error': str(error), **conn_info})
            work.put(None)

        threading.Thread(target=reader, daemon=True).start()
        try:
            while (item := work.get()) is not None:
                meta, req_bytes, recv_ns, recv_utc = item
                self.serve_one(conn, conn_info, meta, req_bytes, recv_ns, recv_utc)
        finally:
            conn.close()
            with self.stats_lock:
                self.active -= 1
            self.event({'event': 'connection_close', **conn_info})

    def serve_one(self, conn, conn_info, meta, req_bytes, recv_ns, recv_utc):
        problems = validate_request(meta, framing.MAX_FRAME_BYTES)
        if self.args.run_id and meta.get('run_id') != self.args.run_id:
            problems.append(f'run_id {meta.get("run_id")!r} != expected {self.args.run_id!r}')
        start_ns = time.monotonic_ns()
        if problems:
            status, resp_size, fault = STATUS_INVALID_REQ, min_response_bytes(), None
        else:
            status, resp_size, fault = STATUS_OK, meta['resp_size_bytes'], None
            delay = meta['service_delay_ms'] / 1000
            if delay > 0:
                time.sleep(delay)
            if self.args.fault != 'none' and meta.get('seq') == self.args.fault_seq:
                fault = self.args.fault
        send_ns = time.monotonic_ns()
        resp = response_meta(meta, self.args.host_name, status, recv_ns, start_ns, send_ns)
        if fault == 'wrong-id':
            resp['req_id'] = f'{resp["req_id"]}-WRONG'
        elif fault == 'short-response':
            resp_size = max(min_response_bytes(), resp_size - 100)
        frame = framing.encode(resp, resp_size)
        try:
            conn.sendall(frame)
            sent_ok = True
        except OSError as error:
            sent_ok = False
            self.event({'event': 'send_error', 'error': str(error), 'req_id': meta.get('req_id'), **conn_info})
        done_ns = time.monotonic_ns()
        with self.stats_lock:
            self.served += 1
            if status == STATUS_OK and sent_ok:
                self.valid += 1
            else:
                self.invalid += 1
            if fault:
                self.faults += 1
        self.event({'event': 'request', 'recv_utc': recv_utc, 'run_id': meta.get('run_id'),
                    'config_id': meta.get('config_id'), 'req_id': meta.get('req_id'),
                    'flow_id': meta.get('flow_id'), 'seq': meta.get('seq'),
                    'client_host': meta.get('client_host'), 'server_host': self.args.host_name, **conn_info,
                    'req_bytes_received': req_bytes, 'resp_size_requested': meta.get('resp_size_bytes'),
                    'resp_bytes_sent': len(frame) if sent_ok else 0,
                    'service_delay_ms_requested': meta.get('service_delay_ms'),
                    'server_recv_mono_ns': recv_ns, 'server_service_start_mono_ns': start_ns,
                    'server_send_mono_ns': send_ns, 'server_sendall_done_mono_ns': done_ns,
                    'server_queue_ms': resp['server_queue_ms'], 'server_service_ms': resp['server_service_ms'],
                    'server_proc_ms': resp['server_proc_ms'], 'status': status, 'problems': problems,
                    'fault_injected': fault})

    def run(self):
        a = self.args
        started_utc, started = utc_iso(), time.monotonic()
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((a.bind, a.port))
        listener.listen(64)
        self.event({'event': 'listening', 'bind': a.bind, 'port': a.port, 'run_id': a.run_id,
                    'host_name': a.host_name, 'fault': a.fault, 'fault_seq': a.fault_seq})
        print(json.dumps({'event': 'listening', 'port': a.port}), flush=True)
        timed_out = False
        threads = []
        with selectors.DefaultSelector() as sel:
            sel.register(listener, selectors.EVENT_READ)
            while True:
                with self.stats_lock:
                    done = a.expect_requests and self.served >= a.expect_requests and self.active == 0
                if done:
                    break
                if time.monotonic() - started > a.max_runtime:
                    timed_out = bool(a.expect_requests)
                    break
                for _key, _ in sel.select(timeout=0.1):
                    conn, peer = listener.accept()
                    with self.stats_lock:
                        self.active += 1
                    t = threading.Thread(target=self.handle, args=(conn, peer), daemon=True)
                    t.start()
                    threads.append(t)
        listener.close()
        for t in threads:
            t.join(timeout=2)
        ok = (not timed_out and self.protocol_errors == 0 and self.invalid == 0
              and (not a.expect_requests or self.valid == a.expect_requests))
        summary = {'run_id': a.run_id, 'host_name': a.host_name, 'port': a.port, 'started_utc': started_utc,
                   'finished_utc': utc_iso(), 'expect_requests': a.expect_requests, 'served': self.served,
                   'valid': self.valid, 'invalid': self.invalid, 'protocol_errors': self.protocol_errors,
                   'timed_out': timed_out, 'fault': a.fault, 'fault_seq': a.fault_seq,
                   'faults_injected': self.faults, 'exit_code': 0 if ok else 1}
        (self.out / 'server-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        self.log.close()
        print(json.dumps(summary), flush=True)
        return summary['exit_code']


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--host-name', required=True, choices=['a1', 'a2'])
    p.add_argument('--bind', default='0.0.0.0')
    p.add_argument('--port', type=int, default=8000)
    p.add_argument('--run-id', default=None, help='reject requests from another run')
    p.add_argument('--out', required=True, help='directory for server-events.jsonl and server-summary.json')
    p.add_argument('--expect-requests', type=int, default=0, help='exit after this many requests (0: run until --max-runtime)')
    p.add_argument('--max-runtime', type=float, default=60, help='seconds')
    p.add_argument('--fault', choices=['none', 'wrong-id', 'short-response'], default='none',
                   help='NEGATIVE CONTROL ONLY: corrupt the response to request --fault-seq')
    p.add_argument('--fault-seq', type=int, default=3)
    args = p.parse_args()
    try:
        return Server(args).run()
    except OSError as error:
        print(json.dumps({'event': 'fatal', 'error': str(error)}), flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
