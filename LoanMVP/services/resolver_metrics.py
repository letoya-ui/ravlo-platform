import time
from collections import defaultdict

_metrics = defaultdict(lambda: {"count": 0, "ok": 0, "error": 0, "total_ms": 0.0})

def record_resolver_result(label: str, status: str, elapsed: float):
    m = _metrics[label]
    m["count"] += 1
    if status == "ok":
        m["ok"] += 1
    else:
        m["error"] += 1
    m["total_ms"] += elapsed * 1000.0

def get_metrics_snapshot():
    snapshot = {}
    for label, m in _metrics.items():
        avg_ms = m["total_ms"] / m["count"] if m["count"] else 0
        snapshot[label] = {
            "count": m["count"],
            "ok": m["ok"],
            "error": m["error"],
            "avg_ms": round(avg_ms, 1),
        }
    return snapshot
