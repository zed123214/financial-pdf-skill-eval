"""Offline run timeline trace utilities.

The trace is intentionally file-based and read-only friendly: pipeline runs append
JSONL events, and the dashboard later reads those events without triggering work.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRACE_RELATIVE_PATH = Path("trace") / "events.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def trace_path_for_output(output_dir: str | Path) -> Path:
    return Path(output_dir) / TRACE_RELATIVE_PATH


class RunTraceWriter:
    def __init__(self, path: str | Path, *, case_id: str, backend: str) -> None:
        self.path = Path(path)
        self.case_id = case_id
        self.backend = backend

    def emit(
        self,
        kind: str,
        *,
        stage: str | None = None,
        status: str | None = None,
        duration_ms: int | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "ts": _now_iso(),
            "case_id": self.case_id,
            "backend": self.backend,
            "kind": kind,
            "stage": stage,
            "status": status,
            "duration_ms": duration_ms,
            "data": data or {},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event


def read_events(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            events.append(data)
    return events


def build_trace_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    finished = [e for e in events if e.get("kind") == "stage_finished"]
    stages = [
        {
            "stage": e.get("stage"),
            "status": e.get("status"),
            "duration_ms": e.get("duration_ms"),
        }
        for e in finished
    ]
    total_duration = 0
    for e in finished:
        duration = e.get("duration_ms")
        if isinstance(duration, (int, float)):
            total_duration += int(duration)
    return {
        "event_count": len(events),
        "stage_count": len(finished),
        "failed_count": sum(1 for e in finished if e.get("status") == "failed"),
        "skipped_count": sum(1 for e in finished if e.get("status") == "skipped"),
        "warning_count": sum(1 for e in finished if e.get("status") == "warning"),
        "total_duration_ms": total_duration,
        "stages": stages,
    }


def load_trace_bundle(output_dir: str | Path | None) -> dict[str, Any]:
    if output_dir is None:
        return {
            "path": None,
            "exists": False,
            "events": [],
            "summary": build_trace_summary([]),
        }
    path = trace_path_for_output(output_dir)
    events = read_events(path)
    return {
        "path": str(path),
        "exists": path.exists(),
        "events": events,
        "summary": build_trace_summary(events),
    }
