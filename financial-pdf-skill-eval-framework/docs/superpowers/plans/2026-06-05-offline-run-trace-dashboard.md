# Offline Run Trace Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline historical trace timeline for each evaluated PDF case and expose it in the existing Streamlit dashboard for project closeout demos.

**Architecture:** Pipeline runs write a per-case JSONL timeline under the case `output_dir` without changing scoring semantics. The dashboard bundle remains read-only and loads the timeline into each case entry. Streamlit renders a new Trace tab with stage metrics, event table, and raw event details.

**Tech Stack:** Python 3, pytest, JSONL, Streamlit, pandas.

---

## File Structure

- Create `framework/run_trace.py`: trace record normalization, JSONL writing, JSONL reading, and stage summary building.
- Modify `framework/pipeline.py`: emit timeline events around existing stages while preserving existing return values and failure behavior.
- Modify `framework/dashboard_bundle.py`: read `<output_dir>/trace/events.jsonl` and attach `run_trace` to each dashboard case.
- Modify `dashboard/components.py`: render timeline metrics, event table, and raw event details.
- Modify `dashboard/streamlit_app.py`: add the `Run Trace` tab.
- Add `tests/test_run_trace.py`: unit tests for writer/reader/summary.
- Modify `tests/test_09_pipeline_fixture.py`: assert pipeline writes trace events for a fixture run.
- Modify `tests/test_dashboard_bundle.py`: assert bundle exposes `run_trace` without evaluating anything.

## Task 1: Run Trace Core

**Files:**
- Create: `framework/run_trace.py`
- Test: `tests/test_run_trace.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_run_trace.py` with tests that expect:

```python
def test_trace_writer_writes_jsonl_events(tmp_path):
    path = tmp_path / "trace" / "events.jsonl"
    writer = run_trace.RunTraceWriter(path, case_id="demo", backend="fixture")
    writer.emit("stage_started", stage="invoke", status="running", data={"backend": "fixture"})
    writer.emit("stage_finished", stage="invoke", status="success", duration_ms=3, data={"output_dir": "out"})
    events = run_trace.read_events(path)
    assert [e["kind"] for e in events] == ["stage_started", "stage_finished"]
    assert events[0]["case_id"] == "demo"
    assert events[1]["duration_ms"] == 3


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
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_run_trace.py -q
```

Expected: failure because `framework.run_trace` does not exist.

- [ ] **Step 3: Implement `framework/run_trace.py`**

Implement:

```python
class RunTraceWriter:
    def __init__(self, path: Path, *, case_id: str, backend: str) -> None: ...
    def emit(self, kind: str, *, stage: str | None = None, status: str | None = None,
             duration_ms: int | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]: ...

def read_events(path: str | Path) -> list[dict[str, Any]]: ...
def trace_path_for_output(output_dir: str | Path) -> Path: ...
def build_trace_summary(events: list[dict[str, Any]]) -> dict[str, Any]: ...
def load_trace_bundle(output_dir: str | Path | None) -> dict[str, Any]: ...
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_run_trace.py -q
```

Expected: all tests in `tests/test_run_trace.py` pass.

## Task 2: Pipeline Trace Emission

**Files:**
- Modify: `framework/pipeline.py`
- Modify: `tests/test_09_pipeline_fixture.py`

- [ ] **Step 1: Add failing fixture test**

Add a test that runs a sandboxed fixture case and asserts:

```python
trace_path = sandbox / "trace" / "events.jsonl"
assert trace_path.exists()
events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
assert events[0]["kind"] == "run_started"
assert events[-1]["kind"] == "run_finished"
assert "invoke" in {event.get("stage") for event in events}
assert "compute_score" in {event.get("stage") for event in events}
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
python -m pytest tests/test_09_pipeline_fixture.py::test_pipeline_writes_offline_run_trace -q
```

Expected: failure because the trace file is not written.

- [ ] **Step 3: Add trace hooks to `run_pipeline()`**

Import `framework.run_trace`, create a writer once the invocation output directory is known, and emit:

- `run_started`
- `stage_started`
- `stage_finished`
- `run_finished`

Do not alter stage order, score calculation, Judge behavior, or failure status decisions.

- [ ] **Step 4: Run fixture tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_09_pipeline_fixture.py -q
```

Expected: fixture pipeline tests pass.

## Task 3: Dashboard Bundle Integration

**Files:**
- Modify: `framework/dashboard_bundle.py`
- Modify: `tests/test_dashboard_bundle.py`

- [ ] **Step 1: Add failing bundle test**

Add a test that creates a temporary output dir with `trace/events.jsonl`, monkeypatches one case to use it, and asserts:

```python
assert "run_trace" in case_entry
assert case_entry["run_trace"]["path"].endswith("trace/events.jsonl")
assert case_entry["run_trace"]["summary"]["event_count"] == 1
assert case_entry["run_trace"]["events"][0]["kind"] == "run_started"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
python -m pytest tests/test_dashboard_bundle.py::test_case_entry_includes_run_trace_from_output_dir -q
```

Expected: failure because `run_trace` is not attached.

- [ ] **Step 3: Implement bundle loading**

Import `framework.run_trace` in `dashboard_bundle.py`, call `load_trace_bundle(output_dir)` inside `_load_one_case()`, and include `"run_trace": run_trace_bundle` in `case_entry`.

- [ ] **Step 4: Run dashboard bundle tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_dashboard_bundle.py -q
```

Expected: dashboard bundle tests pass.

## Task 4: Streamlit Trace UI

**Files:**
- Modify: `dashboard/components.py`
- Modify: `dashboard/streamlit_app.py`

- [ ] **Step 1: Add render helper**

Add `render_run_trace(run_trace: dict) -> None` to `dashboard/components.py`. It should:

- show metrics for event count, stage count, failed count, total duration
- show a dataframe of events with `ts`, `stage`, `kind`, `status`, `duration_ms`
- show raw event JSON expanders
- show a friendly info message when no trace exists

- [ ] **Step 2: Add dashboard tab**

In `dashboard/streamlit_app.py`, add `_render_run_trace()` and include a `Run Trace` tab between overview and Judge.

- [ ] **Step 3: Import smoke check**

Run:

```powershell
python -m pytest tests/test_dashboard_bundle.py -q
python - <<'PY'
import dashboard.streamlit_app
print("streamlit import ok")
PY
```

Expected: tests pass and the Streamlit module imports without a syntax error.

## Task 5: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_run_trace.py tests/test_09_pipeline_fixture.py tests/test_dashboard_bundle.py -q
```

Expected: targeted tests pass.

- [ ] **Step 2: Rebuild dashboard bundle**

Run:

```powershell
python run.py --build-dashboard-bundle
```

Expected: `reports/dashboard/dashboard_bundle.json` is written and includes `run_trace` for cases with trace files.

- [ ] **Step 3: Run offline suite**

Run:

```powershell
python -m pytest -m offline -q
```

Expected: offline suite passes or any failures are explicitly reported with exact failing tests.

## Self-Review

- Spec coverage: pipeline trace, bundle read-only loading, and Streamlit UI are covered.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: trace fields use `case_id`, `backend`, `kind`, `stage`, `status`, `duration_ms`, `data`, `summary`, and `events` consistently.
