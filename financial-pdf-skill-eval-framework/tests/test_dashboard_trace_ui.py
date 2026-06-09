from __future__ import annotations

import pytest

from dashboard import components as C

pytestmark = pytest.mark.offline


def test_run_trace_event_rows_keep_demo_fields():
    events = [
        {
            "ts": "2026-06-05T10:11:12.123456+00:00",
            "case_id": "demo",
            "backend": "fixture",
            "kind": "stage_finished",
            "stage": "invoke",
            "status": "success",
            "duration_ms": 12,
            "data": {"output_dir": "out"},
        }
    ]

    rows = C.run_trace_event_rows(events)

    assert rows == [
        {
            "time": "10:11:12",
            "stage": "invoke",
            "kind": "stage_finished",
            "status": "success",
            "duration_ms": 12,
            "detail": "output_dir=out",
        }
    ]


def test_run_trace_event_rows_summarize_errors_first():
    events = [
        {
            "ts": "2026-06-05T10:11:12+00:00",
            "kind": "stage_finished",
            "stage": "assert_outputs",
            "status": "failed",
            "duration_ms": 4,
            "data": {"errors": ["output_contract: missing parsed.md"], "failed": 1},
        }
    ]

    rows = C.run_trace_event_rows(events)

    assert rows[0]["detail"] == "errors=output_contract: missing parsed.md"
