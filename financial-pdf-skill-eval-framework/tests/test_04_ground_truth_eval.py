"""Ground Truth evaluator coverage."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest

from framework.context import FRAMEWORK_ROOT, load_config
from framework.gt_evaluator import evaluate, filter_metrics, normalize_number


def test_evaluate_with_ground_truth_help():
    cfg = load_config()
    proc = subprocess.run([sys.executable, str(cfg.skill.gt_eval_script), "--help"], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0
    assert "--financial-summary" in proc.stdout
    assert "--ground-truth" in proc.stdout
    assert "--output" in proc.stdout


@pytest.mark.parametrize("raw,expected", [
    ("1,234.56", 1234.56),
    ("1，234.56", 1234.56),
    ("(18,970,274.67)", -18970274.67),
    ("（18，970，274.67）", -18970274.67),
    ("-", None),
    ("", None),
    ("75,424,747", 75424747.0),
])
def test_normalize_number(raw, expected):
    assert normalize_number(raw) == expected


@pytest.mark.fixture
@pytest.mark.offline
def test_evaluate_with_real_fixture_no_gt_returns_no_ground_truth(tmp_path):
    """BYD fixture has no filled Ground Truth yet -> should not fail; should report no_ground_truth."""
    fixture = FRAMEWORK_ROOT / "data" / "real_las_outputs" / "byd_caibao"
    if not fixture.exists():
        pytest.skip("BYD fixture not imported")
    gt = FRAMEWORK_ROOT / "evaluation" / "ground_truth" / "byd_manual_gt.json"
    res = evaluate(fixture, gt)
    # All expected fields are empty -> treated as no_ground_truth
    assert res.get("no_ground_truth") is True or res.get("status") in {"no_ground_truth", "skipped"}


@pytest.mark.offline
def test_filter_metrics_returns_eligible_and_skipped():
    metrics = [
        {"statement": "BS", "item": "现金", "period": "2024", "expected": "100.00"},
        {"statement": "BS", "item": "应收", "period": "2024", "expected": ""},
        {"statement": "BS", "item": "存货", "period": "2024", "expected": "  "},
        {"statement": "BS", "item": "总计", "period": "2024", "expected": None},
        {"statement": "BS", "item": "负债", "period": "2024", "expected": "50.00"},
    ]
    eligible, skipped = filter_metrics(metrics)
    assert len(eligible) == 2
    assert len(skipped) == 3
    for item in skipped:
        assert {"statement", "item", "period"} <= set(item)


@pytest.mark.offline
def test_evaluate_byd_todo_returns_no_ground_truth_with_skipped_items():
    """BYD GT is source=todo_manual_verify with empty expected — must NOT crash
    and must report skipped_expected_items so the report can surface the gap."""
    fixture = FRAMEWORK_ROOT / "data" / "real_las_outputs" / "byd_caibao"
    if not fixture.exists():
        pytest.skip("BYD fixture not imported")
    gt = FRAMEWORK_ROOT / "evaluation" / "ground_truth" / "byd_manual_gt.json"
    res = evaluate(fixture, gt)
    assert res.get("no_ground_truth") is True
    assert res.get("eligible_count") == 0
    skipped = res.get("skipped_expected_items") or []
    # BYD template has 5 todo_manual_verify entries.
    assert len(skipped) >= 1, res


@pytest.mark.offline
def test_evaluate_mixed_expected_only_counts_filled_in_denominator(tmp_path):
    """Manual-source GT with both filled and empty expected must filter before
    calling the Skill, so eligible_count = #filled and accuracy denominator
    reflects only those entries."""
    fixture = FRAMEWORK_ROOT / "data" / "real_las_outputs" / "byd_caibao"
    if not fixture.exists():
        pytest.skip("BYD fixture not imported")
    summary_path = fixture / "normalized" / "financial_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    metrics = summary.get("metrics", [])
    if not metrics:
        pytest.skip("financial_summary.json has no metrics")
    first = metrics[0]
    fake_gt = {
        "case_id": "byd_mixed_gt_smoke",
        "source": "manual",
        "metrics": [
            # one filled (should be matchable against actual summary)
            {
                "statement": first.get("statement"),
                "item": first.get("item"),
                "period": first.get("period"),
                "expected": first.get("value"),
                "evidence": "harness_only",
            },
            # one empty (must be filtered into skipped_expected_items)
            {
                "statement": "Filler",
                "item": "TODO",
                "period": "2099-12-31",
                "expected": "",
                "evidence": "harness_only",
            },
        ],
    }
    gt_path = tmp_path / "mixed_gt.json"
    gt_path.write_text(json.dumps(fake_gt, ensure_ascii=False), encoding="utf-8")
    fake_fixture = tmp_path / "fake_byd_mixed"
    shutil.copytree(fixture, fake_fixture)
    res = evaluate(fake_fixture, gt_path)
    assert res.get("status") == "success", res
    assert res.get("eligible_count") == 1, res
    assert len(res.get("skipped_expected_items", [])) == 1
    # On-disk gt_eval_result.json must also carry the eligibility annotations.
    gt_eval_path = fake_fixture / "evaluation" / "gt_eval_result.json"
    assert gt_eval_path.exists()
    written = json.loads(gt_eval_path.read_text(encoding="utf-8"))
    assert written.get("eligible_count") == 1
    assert "skipped_expected_items" in written


@pytest.mark.fixture
@pytest.mark.offline
def test_evaluate_emits_gt_eval_result_when_expected_filled(tmp_path):
    fixture = FRAMEWORK_ROOT / "data" / "real_las_outputs" / "byd_caibao"
    if not fixture.exists():
        pytest.skip("BYD fixture not imported")
    summary_path = fixture / "normalized" / "financial_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    metrics = summary.get("metrics", [])
    if not metrics:
        pytest.skip("financial_summary.json has no metrics")
    # Build a partial GT from the actual extraction so we can exercise the success path
    # (this is purely an evaluator harness test, not a true accuracy measurement)
    first = metrics[0]
    # We use source: "manual" only because the gt_evaluator gate refuses any other
    # source. This GT lives in tmp_path, is never copied to the real fixture, and is
    # destroyed when the test finishes. The fixture pollution sanity check below
    # ensures no harness accuracy ever leaks into reports.
    fake_gt = {
        "case_id": "byd_caibao_evaluator_mechanics_smoke",
        "source": "manual",
        "note": "tmp_path harness only; never use as real GT",
        "metrics": [
            {
                "statement": first.get("statement"),
                "item": first.get("item"),
                "period": first.get("period"),
                "expected": first.get("value"),
                "evidence": "harness_only",
            }
        ],
    }
    gt_path = tmp_path / "harness_gt.json"
    gt_path.write_text(json.dumps(fake_gt, ensure_ascii=False), encoding="utf-8")
    real_gt_eval = fixture / "evaluation" / "gt_eval_result.json"
    before_real_gt_eval = real_gt_eval.read_text(encoding="utf-8") if real_gt_eval.exists() else None
    # IMPORTANT: copy the fixture into tmp_path so the Skill's gt eval writes
    # gt_eval_result.json into the COPY, not into the real fixture. Writing harness
    # accuracy back into data/real_las_outputs/* would poison fixture credibility.
    fake_fixture = tmp_path / "fake_byd_for_evaluator_smoke"
    shutil.copytree(fixture, fake_fixture)
    res = evaluate(fake_fixture, gt_path)
    assert res.get("status") == "success", res
    assert "numeric_accuracy" in res
    # Sanity: the real fixture must NOT have been touched by this harness run.
    after_real_gt_eval = real_gt_eval.read_text(encoding="utf-8") if real_gt_eval.exists() else None
    assert after_real_gt_eval == before_real_gt_eval, (
        "test polluted the real fixture with harness-only accuracy; this would mislead reports"
    )
