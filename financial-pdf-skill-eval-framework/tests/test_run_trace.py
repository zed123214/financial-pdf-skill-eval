from __future__ import annotations

import pytest

from framework import run_trace

pytestmark = pytest.mark.offline


def test_trace_writer_writes_jsonl_events(tmp_path):
    path = tmp_path / "trace" / "events.jsonl"
    writer = run_trace.RunTraceWriter(path, case_id="demo", backend="fixture")

    writer.emit(
        "stage_started",
        stage="invoke",
        status="running",
        data={"backend": "fixture"},
    )
    writer.emit(
        "stage_finished",
        stage="invoke",
        status="success",
        duration_ms=3,
        data={"output_dir": "out"},
    )

    events = run_trace.read_events(path)

    assert [e["kind"] for e in events] == ["stage_started", "stage_finished"]
    assert events[0]["case_id"] == "demo"
    assert events[0]["backend"] == "fixture"
    assert events[0]["stage"] == "invoke"
    assert events[1]["duration_ms"] == 3
    assert events[1]["data"] == {"output_dir": "out"}


def test_build_summary_counts_status_and_duration(tmp_path):
    path = tmp_path / "events.jsonl"
    writer = run_trace.RunTraceWriter(path, case_id="demo", backend="fixture")
    writer.emit("stage_finished", stage="invoke", status="success", duration_ms=5)
    writer.emit("stage_finished", stage="compute_score", status="failed", duration_ms=7)

    summary = run_trace.build_trace_summary(run_trace.read_events(path))

    assert summary["event_count"] == 2
    assert summary["stage_count"] == 2
    assert summary["failed_count"] == 1
    assert summary["total_duration_ms"] == 12
    assert summary["stages"] == [
        {"stage": "invoke", "status": "success", "duration_ms": 5},
        {"stage": "compute_score", "status": "failed", "duration_ms": 7},
    ]


def test_load_trace_bundle_returns_empty_shape_for_missing_output_dir(tmp_path):
    missing = tmp_path / "missing"

    bundle = run_trace.load_trace_bundle(missing)

    assert bundle["path"] == str(missing / "trace" / "events.jsonl")
    assert bundle["events"] == []
    assert bundle["summary"]["event_count"] == 0
    assert bundle["exists"] is False
