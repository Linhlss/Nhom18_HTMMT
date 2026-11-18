"""Request/response metadata for protocol tcp-binary-v1 (docs/workload-spec.md §4)."""
from workload.framing import min_frame_bytes

PROTOCOL = 'tcp-binary-v1'
MAX_ID_CHARS = 64
MAX_SEQ = 10**9 - 1
MAX_SERVICE_DELAY_MS = 10_000.0
STATUS_OK = 'OK'
STATUS_INVALID_REQ = 'ERR_INVALID_REQ'

REQUEST_FIELDS = {
    'msg': str, 'protocol': str, 'run_id': str, 'config_id': str, 'req_id': str, 'flow_id': int,
    'seq': int, 'client_host': str, 'client_send_utc': str, 'resp_size_bytes': int,
    'service_delay_ms': (int, float),
}


def req_id(run_id, flow_id, seq):
    return f'{run_id}_f{flow_id}_r{seq}'


def request_meta(run_id, config_id, flow_id, seq, client_host, send_utc, resp_size_bytes, service_delay_ms):
    return {'msg': 'request', 'protocol': PROTOCOL, 'run_id': run_id, 'config_id': config_id,
            'req_id': req_id(run_id, flow_id, seq), 'flow_id': flow_id, 'seq': seq,
            'client_host': client_host, 'client_send_utc': send_utc,
            'resp_size_bytes': resp_size_bytes, 'service_delay_ms': float(service_delay_ms)}


def response_meta(request, server_host, status, recv_ns, start_ns, send_ns):
    return {'msg': 'response', 'protocol': PROTOCOL,
            'run_id': request.get('run_id'), 'req_id': request.get('req_id'),
            'flow_id': request.get('flow_id'), 'seq': request.get('seq'),
            'server_host': server_host, 'status': status,
            'server_recv_mono_ns': recv_ns, 'server_service_start_mono_ns': start_ns,
            'server_send_mono_ns': send_ns,
            'server_queue_ms': round((start_ns - recv_ns) / 1e6, 6),
            'server_service_ms': round((send_ns - start_ns) / 1e6, 6),
            'server_proc_ms': round((send_ns - recv_ns) / 1e6, 6)}


def _worst_ids():
    long_id = 'r' * MAX_ID_CHARS
    return long_id, 'k' * MAX_ID_CHARS


def min_request_bytes():
    run_id, config_id = _worst_ids()
    meta = request_meta(run_id, config_id, 7, MAX_SEQ, 'c1', '2026-01-01T00:00:00.000000Z',
                        16 * 1024 * 1024, 12345.678901)
    return min_frame_bytes(meta)


def min_response_bytes():
    run_id, _ = _worst_ids()
    big = 10**19 - 1
    request = {'run_id': run_id, 'req_id': req_id(run_id, 7, MAX_SEQ), 'flow_id': 7, 'seq': MAX_SEQ}
    meta = response_meta(request, 'a1', STATUS_INVALID_REQ, big - 10**12, big - 10**6, big)
    return min_frame_bytes(meta)


def validate_request(meta, max_frame_bytes):
    """Return list of problems (empty when valid)."""
    problems = []
    for key, kind in REQUEST_FIELDS.items():
        value = meta.get(key)
        if not isinstance(value, kind) or isinstance(value, bool):
            problems.append(f'{key} missing or wrong type')
    if problems:
        return problems
    if meta['msg'] != 'request' or meta['protocol'] != PROTOCOL:
        problems.append('not a tcp-binary-v1 request')
    if meta['req_id'] != req_id(meta['run_id'], meta['flow_id'], meta['seq']):
        problems.append('req_id does not match run_id/flow_id/seq')
    if not min_response_bytes() <= meta['resp_size_bytes'] <= max_frame_bytes:
        problems.append(f'resp_size_bytes {meta["resp_size_bytes"]} outside '
                        f'[{min_response_bytes()}, {max_frame_bytes}]')
    if not 0 <= meta['service_delay_ms'] <= MAX_SERVICE_DELAY_MS:
        problems.append('service_delay_ms outside [0, 10000]')
    return problems
