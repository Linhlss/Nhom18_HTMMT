"""Statistics shared by workload and measurement (definitions in docs/metrics-spec.md §6)."""
import math


def percentile_nearest_rank(values, p):
    """Nearest-rank percentile: sort ascending, rank = ceil(p/100 * n), return the rank-th value.

    Returns None for an empty sample (never 0). p must be in (0, 100]."""
    if not 0 < p <= 100:
        raise ValueError('p must be in (0, 100]')
    data = sorted(v for v in values if v is not None)
    if not data:
        return None
    rank = max(1, math.ceil(p / 100 * len(data)))
    return data[rank - 1]


def describe(values):
    """count/min/mean/p50/p95/p99/max with nearest-rank percentiles; None when no samples."""
    data = [v for v in values if v is not None]
    if not data:
        return {'count': 0, 'min': None, 'mean': None, 'p50': None, 'p95': None, 'p99': None, 'max': None}
    return {'count': len(data), 'min': min(data), 'mean': sum(data) / len(data),
            'p50': percentile_nearest_rank(data, 50), 'p95': percentile_nearest_rank(data, 95),
            'p99': percentile_nearest_rank(data, 99), 'max': max(data)}
