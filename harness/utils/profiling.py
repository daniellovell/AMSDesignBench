from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Tuple


_TRUE_STRINGS = {"1", "true", "yes", "on"}
_ENABLE_ENV_KEY = "ENABLE_PROFILING"


def _env_enabled() -> bool:
    return os.getenv(_ENABLE_ENV_KEY, "").strip().lower() in _TRUE_STRINGS


_ENABLED: bool = _env_enabled()
_ENTRIES: list[dict[str, object]] = []
_LOCK = threading.Lock()


def is_enabled() -> bool:
    """Return whether profiling logs are enabled."""

    return _ENABLED


def set_enabled(value: bool) -> None:
    """Enable/disable profiling globally and synchronize the env var."""

    global _ENABLED
    _ENABLED = bool(value)
    if _ENABLED:
        os.environ[_ENABLE_ENV_KEY] = "1"
    else:
        os.environ.pop(_ENABLE_ENV_KEY, None)
    with _LOCK:
        _ENTRIES.clear()


def log(component: str, operation: str, duration_ms: float, context: Optional[str] = None) -> None:
    """Emit a formatted profiling log line if profiling is enabled."""

    if not _ENABLED:
        return
    entry = {
        "timestamp": time.time(),
        "component": component,
        "operation": operation,
        "duration_ms": float(duration_ms),
        "context": context or "",
        "thread_id": threading.get_ident(),
    }
    with _LOCK:
        _ENTRIES.append(entry)
    suffix = f" {context}" if context else ""
    print(f"[PROFILE] {component} {operation} {duration_ms:.0f}ms{suffix}", file=sys.stderr, flush=True)


def write_reports(output_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """Persist profiling entries and return paths to log and summary files."""

    if not _ENABLED:
        return (None, None)
    with _LOCK:
        entries = list(_ENTRIES)
    if not entries:
        return (None, None)

    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "profiling_log.jsonl"
    summary_path = output_dir / "profiling_summary.txt"

    with log_path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Aggregate statistics by component+operation
    aggregates: dict[tuple[str, str], dict[str, float]] = {}
    for entry in entries:
        key = (entry["component"], entry["operation"])
        agg = aggregates.setdefault(key, {"count": 0.0, "total_ms": 0.0, "max_ms": 0.0})
        dur = float(entry["duration_ms"])
        agg["count"] += 1
        agg["total_ms"] += dur
        if dur > agg["max_ms"]:
            agg["max_ms"] = dur

    # Write summary sorted by descending total duration
    rows = sorted(
        [
            (
                comp,
                op,
                stats["count"],
                stats["total_ms"],
                stats["total_ms"] / stats["count"],
                stats["max_ms"],
            )
            for (comp, op), stats in aggregates.items()
        ],
        key=lambda item: item[3],
        reverse=True,
    )

    with summary_path.open("w", encoding="utf-8") as f:
        f.write("Component\tOperation\tCount\tTotal ms\tAvg ms\tMax ms\n")
        for comp, op, count, total_ms, avg_ms, max_ms in rows:
            f.write(
                f"{comp}\t{op}\t{int(count)}\t{total_ms:.1f}\t{avg_ms:.1f}\t{max_ms:.1f}\n"
            )

    return (log_path, summary_path)
