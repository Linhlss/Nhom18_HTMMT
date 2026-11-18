"""Frame format tcp-binary-v1 shared by client and server (docs/workload-spec.md §4).

Frame = header (8 bytes) + JSON metadata (UTF-8) + padding.
header = meta_len (uint32, network byte order) + pad_len (uint32, network byte order).
frame_bytes = 8 + meta_len + pad_len, and the metadata carries "frame_bytes"
so the receiver can verify the size it was asked to produce.
"""
import json
import struct

HEADER = struct.Struct('!II')
HEADER_BYTES = HEADER.size  # 8
MAX_META_BYTES = 64 * 1024
MAX_FRAME_BYTES = 16 * 1024 * 1024
PAD_BYTE = b'X'


class FrameError(ValueError):
    """Malformed frame or impossible size request."""


def _meta_bytes(meta):
    return json.dumps(meta, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')


def encode(meta, frame_bytes):
    """Return a frame of exactly frame_bytes bytes; raise if metadata does not fit."""
    if not isinstance(frame_bytes, int) or isinstance(frame_bytes, bool):
        raise FrameError('frame_bytes must be an integer')
    if frame_bytes > MAX_FRAME_BYTES:
        raise FrameError(f'frame_bytes {frame_bytes} exceeds limit {MAX_FRAME_BYTES}')
    body = dict(meta, frame_bytes=frame_bytes)
    raw = _meta_bytes(body)
    if len(raw) > MAX_META_BYTES:
        raise FrameError(f'metadata {len(raw)} B exceeds limit {MAX_META_BYTES}')
    pad = frame_bytes - HEADER_BYTES - len(raw)
    if pad < 0:
        raise FrameError(f'frame_bytes={frame_bytes} too small: header {HEADER_BYTES} B + '
                         f'metadata {len(raw)} B = {HEADER_BYTES + len(raw)} B')
    return HEADER.pack(len(raw), pad) + raw + PAD_BYTE * pad


def min_frame_bytes(meta):
    """Smallest frame that can carry this metadata (worst case for numeric width is caller's job)."""
    # frame_bytes itself is serialized; use a 9-digit placeholder as upper bound for <= 16 MiB.
    return HEADER_BYTES + len(_meta_bytes(dict(meta, frame_bytes=MAX_FRAME_BYTES)))


def _recv_exact(sock, n):
    chunks = []
    remaining = n
    while remaining:
        chunk = sock.recv(min(remaining, 1 << 20))
        if not chunk:
            raise ConnectionError(f'peer closed connection with {remaining} of {n} bytes outstanding')
        chunks.append(chunk)
        remaining -= len(chunk)
    return b''.join(chunks)


def read_frame(sock):
    """Read one frame. Returns (meta, total_bytes_read). Raises EOFError on clean close."""
    first = sock.recv(HEADER_BYTES)
    if not first:
        raise EOFError('connection closed between frames')
    header = first if len(first) == HEADER_BYTES else first + _recv_exact(sock, HEADER_BYTES - len(first))
    meta_len, pad_len = HEADER.unpack(header)
    if meta_len == 0 or meta_len > MAX_META_BYTES:
        raise FrameError(f'invalid meta_len {meta_len}')
    total = HEADER_BYTES + meta_len + pad_len
    if total > MAX_FRAME_BYTES:
        raise FrameError(f'frame of {total} B exceeds limit')
    raw = _recv_exact(sock, meta_len)
    remaining = pad_len
    while remaining:  # discard padding without holding it in memory
        chunk = sock.recv(min(remaining, 1 << 20))
        if not chunk:
            raise ConnectionError(f'peer closed connection inside padding ({remaining} B left)')
        remaining -= len(chunk)
    try:
        meta = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FrameError(f'metadata is not UTF-8 JSON: {error}') from error
    if not isinstance(meta, dict):
        raise FrameError('metadata must be a JSON object')
    if meta.get('frame_bytes') != total:
        raise FrameError(f'frame_bytes field {meta.get("frame_bytes")!r} != bytes on wire {total}')
    return meta, total
