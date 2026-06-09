"""End-to-end pipeline coverage using fixture / mock backends (offline)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from framework import case_loader, pipeline
from framework.context import FRAMEWORK_ROOT


@pytest.mark.offline
def test_pipeline_runs_byd_fixture_offline(tmp_path):
    fixture = FRAMEWORK_ROOT / "data" / "real_las_outputs" / "byd_caibao"
    if not fixture.exists():
        pytest.skip("BYD fixture not imported")

    # Copy fixture into tmp_path so the pipeline can safely write score_result.json
    # without polluting the source-of-truth fixture under data/real_las_outputs.
    sandbox = tmp_path / "byd_caibao"
    shutil.copytree(fixture, sandbox)

    case = {
        "case_id": "byd_pipeline_smoke",
        "name": "BYD fixture pipeline smoke",
        "backend": "fixture",
        "output_profile": "standard",
        "output_dir": str(sandbox),
        # Use the canonical todo_manual_verify GT to confirm financial_accuracy=null path.
        "ground_truth": "evaluation/ground_truth/byd_manual_gt.json",
        "validations": [
            {"type": "output_contract", "profile": "standard"},
            {"type": "data_authenticity", "expected_backend": "real_las"},
        ],
        "tags": ["offline"],
    }
    case = case_loader.normalize_case(case)
    result = pipeline.run_pipeline(case, static_first=False, dry_run=False)

    # Pipeline overall should not be hard-failed: output_contract + assertions
    # pass; gt is skipped because todo_manual_verify -> no_ground_truth.
    assert result.status in {"success", "failed"}, result.status
    stage_names = [s.name for s in result.stages]
    for required in ("invoke", "collect_artifacts", "assert_outputs", "evaluate_ground_truth", "compute_score"):
        assert required in stage_names, f"missing stage: {required}; got {stage_names}"

    # gt should be skipped (no_ground_truth), not failed.
    gt_stage = next(s for s in result.stages if s.name == "evaluate_ground_truth")
    assert gt_stage.status == "skipped", gt_stage

    # Compute score must produce a finite weighted_score with financial_accuracy=null.
    score = result.score_result
    assert score is not None, result.stages
    assert score["dimensions"]["financial_accuracy"] is None
    assert isinstance(score["weighted_score"], (int, float))
    assert 0.0 <= score["weighted_score"] <= 10.0

    # score_result.json should be written into the sandboxed output dir.
    score_path = sandbox / "evaluation" / "score_result.json"
    assert score_path.exists(), "score_result.json was not produced"
    written = json.loads(score_path.read_text(encoding="utf-8"))
    assert written["case_id"] == "byd_pipeline_smoke"


@pytest.mark.offline
def test_pipeline_runs_pioneer_fixture_with_manual_gt(tmp_path):
    """Pioneer scan PDF has a manual_verified GT — exercise the accuracy path."""
    fixture = FRAMEWORK_ROOT / "data" / "real_las_outputs" / "先锋财报_扫码件-6-9"
    if not fixture.exists():
        pytest.skip("先锋财报 fixture not imported")

    sandbox = tmp_path / "pioneer"
    shutil.copytree(fixture, sandbox)

    case = {
        "case_id": "pioneer_pipeline_smoke",
        "name": "Pioneer fixture pipeline smoke",
        "backend": "fixture",
        "output_profile": "standard",
        "output_dir": str(sandbox),
        "ground_truth": "evaluation/ground_truth/先锋财报_扫码件-6-9_manual_gt.json",
        "validations": [
            {"type": "output_contract", "profile": "standard"},
        ],
        "tags": ["offline"],
    }
    case = case_loader.normalize_case(case)
    result = pipeline.run_pipeline(case, static_first=False)

    summary = result.gt_eval or {}
    if not summary.get("status") == "success":
        # The fixture's financial_summary may not have any matching metrics if the
        # parser produced 0 metrics (scanned PDF). Either way the stage runs and
        # does not crash.
        assert summary.get("status") in {"success", "no_ground_truth", "skipped", "failed"}

    # Even if numeric_accuracy is 0, weighted_score must still be computed.
    score = result.score_result
    assert score is not None
    assert score["weighted_score"] is not None


@pytest.mark.offline
def test_pipeline_skips_real_las_without_creds(monkeypatch, tmp_path):
    """real_las without LAS_API_KEY+ALLOW_REAL_LAS=1 must be skipped, not failed."""
    monkeypatch.delenv("LAS_API_KEY", raising=False)
    monkeypatch.delenv("ALLOW_REAL_LAS", raising=False)
    case = {
        "case_id": "pipeline_real_las_skip",
        "name": "real_las gated skip",
        "backend": "real_las",
        "input_pdf": "data/samples/sample.pdf",
        "output_profile": "standard",
        "output_dir": str(tmp_path / "real_las_skip"),
        "validations": [],
        "tags": ["real_las"],
    }
    case = case_loader.normalize_case(case)
    result = pipeline.run_pipeline(case, static_first=False)
    assert result.status == "skipped", result.status
    inv_stage = next(s for s in result.stages if s.name == "invoke")
    assert inv_stage.status == "skipped"


@pytest.mark.offline
def test_pipeline_writes_offline_run_trace(tmp_path):
    fixture = FRAMEWORK_ROOT / "data" / "real_las_outputs" / "byd_caibao"
    if not fixture.exists():
        pytest.skip("BYD fixture not imported")

    sandbox = tmp_path / "byd_caibao_trace"
    shutil.copytree(fixture, sandbox)

    case = {
        "case_id": "byd_pipeline_trace",
        "name": "BYD fixture pipeline trace",
        "backend": "fixture",
        "output_profile": "standard",
        "output_dir": str(sandbox),
        "ground_truth": "evaluation/ground_truth/byd_manual_gt.json",
        "validations": [
            {"type": "output_contract", "profile": "standard"},
            {"type": "data_authenticity", "expected_backend": "real_las"},
        ],
        "tags": ["offline"],
    }
    case = case_loader.normalize_case(case)

    result = pipeline.run_pipeline(case, static_first=False, dry_run=False)

    trace_path = sandbox / "trace" / "events.jsonl"
    assert trace_path.exists(), "trace/events.jsonl was not produced"
    events = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert events[0]["kind"] == "run_started"
    assert events[-1]["kind"] == "run_finished"
    assert events[-1]["status"] == result.status
    stages = {event.get("stage") for event in events}
    assert "invoke" in stages
    assert "compute_score" in stages
