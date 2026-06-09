"""Report generation coverage."""
from __future__ import annotations

import pytest

from framework.context import FRAMEWORK_ROOT
from framework import report_collector


@pytest.mark.offline
def test_evaluation_summary_can_be_generated(tmp_path):
    summaries = report_collector.collect_summaries_from_manifest()
    out = tmp_path / "evaluation_summary.md"
    report_collector.write_summary_markdown(summaries, out)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    for marker in [
        "Output completeness is NOT parsing accuracy",
        "real_las costs money",
        "Output Contract",
        "Ground Truth accuracy",
    ]:
        assert marker in text, f"summary missing marker: {marker}"


@pytest.mark.offline
def test_failure_cases_can_be_generated(tmp_path):
    summaries = report_collector.collect_summaries_from_manifest()
    out = tmp_path / "failure_cases.md"
    report_collector.write_failure_cases_markdown(summaries, out)
    assert out.exists()


@pytest.mark.offline
def test_manifest_accuracy_flag_is_preserved(tmp_path, monkeypatch):
    manifest = tmp_path / "dataset_manifest.yaml"
    manifest.write_text(
        "\n".join([
            "real_las_fixtures:",
            "  - case_id: synthetic_fixture",
            "    source_output_dir: data/real_las_outputs/synthetic_fixture",
            "    ground_truth: evaluation/ground_truth/synthetic_fixture_manual_gt.json",
            "    count_as_real_evaluation: false",
        ]),
        encoding="utf-8",
    )

    captured = []

    def fake_summarize_case(case, invocation, validations):
        captured.append(case)
        return {
            "case_id": case["case_id"],
            "count_as_real_evaluation": case.get("count_as_real_evaluation"),
        }

    monkeypatch.setattr(report_collector, "summarize_case", fake_summarize_case)

    summaries = report_collector.collect_summaries_from_manifest(manifest)

    assert captured[0]["count_as_real_evaluation"] is False
    assert summaries[0]["count_as_real_evaluation"] is False


@pytest.mark.offline
def test_summarize_ignores_stale_judge_result_when_default_disabled(tmp_path, monkeypatch):
    out = tmp_path / "case"
    (out / "evaluation").mkdir(parents=True)
    (out / "evaluation" / "judge_result.json").write_text(
        '{"mode": "live", "reading_order_score": 0.9}',
        encoding="utf-8",
    )

    monkeypatch.setattr(report_collector.output_contract, "read_run_meta", lambda output_dir: {})
    monkeypatch.setattr(report_collector.output_contract, "read_quality_checks", lambda output_dir: {})
    monkeypatch.setattr(
        report_collector.output_contract,
        "validate_standard_output",
        lambda output_dir, profile: {"passed": True},
    )
    monkeypatch.setattr(
        report_collector.gt_evaluator,
        "evaluate",
        lambda output_dir, ground_truth: {"status": "no_ground_truth", "no_ground_truth": True},
    )

    summary = report_collector.summarize_case(
        {"case_id": "case", "output_dir": str(out)},
        {"status": "fixture", "output_dir": str(out)},
        [],
    )

    assert summary["judge_result"] is None


@pytest.mark.offline
def test_final_report_can_be_generated(tmp_path):
    summaries = report_collector.collect_summaries_from_manifest()
    out = tmp_path / "final_project_report.md"
    report_collector.write_final_project_report(summaries, out)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Output completeness != parsing accuracy" in text
    assert "real_las costs money" in text
    assert "real_openclaw backend is unverified" in text
