"""Unit tests for the P0 scoring_model (pure functions, mocked JSON)."""
from __future__ import annotations

import pytest

from framework import scoring_model
from framework.scoring_model import ScoreInputs


@pytest.fixture(scope="module")
def profile():
    return scoring_model.load_profile()


def _inputs(**overrides):
    base = dict(
        case_id="t",
        quality_checks={
            "table_statistics": {"raw_table_count": 2, "financial_table_count": 2, "unknown_table_count": 0},
            "metric_statistics": {"metric_record_count": 20},
            "data_authenticity": {"is_synthetic": False, "execution_backend": "real_las"},
        },
        run_meta={"page_count": 2, "status": "success"},
        assertions=[
            {"type": "output_contract", "passed": True, "message": "ok"},
            {"type": "data_authenticity", "passed": True, "message": "ok"},
        ],
        gt_eval={"status": "success", "numeric_accuracy": 0.92, "eligible_count": 5, "no_ground_truth": False},
        case={"case_id": "t", "output_dir": "outputs/t"},
    )
    base.update(overrides)
    return ScoreInputs(**base)


@pytest.mark.offline
def test_output_contract_pass_score(profile):
    s = scoring_model.score_output_contract(_inputs(), profile)
    assert s == profile["boolean_pass_score"]


@pytest.mark.offline
def test_output_contract_fail_score(profile):
    inp = _inputs(assertions=[{"type": "output_contract", "passed": False, "message": "missing"}])
    s = scoring_model.score_output_contract(inp, profile)
    assert s == profile["severity_fail_score"]["high"]


@pytest.mark.offline
def test_table_structure_zero_financial(profile):
    qc = {"table_statistics": {"raw_table_count": 4, "financial_table_count": 0, "unknown_table_count": 4}}
    s = scoring_model.score_table_structure(_inputs(quality_checks=qc), profile)
    assert s == profile["table_structure"]["zero"]


@pytest.mark.offline
def test_table_structure_partial(profile):
    qc = {"table_statistics": {"raw_table_count": 2, "financial_table_count": 1, "unknown_table_count": 0}}
    s = scoring_model.score_table_structure(_inputs(quality_checks=qc), profile)
    assert s == profile["table_structure"]["partial"]


@pytest.mark.offline
def test_table_structure_good(profile):
    qc = {"table_statistics": {"raw_table_count": 2, "financial_table_count": 2, "unknown_table_count": 0}}
    s = scoring_model.score_table_structure(_inputs(quality_checks=qc), profile)
    assert s == profile["table_structure"]["good"]


@pytest.mark.offline
def test_financial_accuracy_linear_map(profile):
    # accuracy 0.92 -> 1 + 9*0.92 = 9.28 -> rounded to 9.3
    s = scoring_model.score_financial_accuracy(_inputs(), profile)
    assert s == pytest.approx(9.3, abs=0.05)


@pytest.mark.offline
def test_financial_accuracy_none_when_no_gt(profile):
    inp = _inputs(gt_eval={"status": "no_ground_truth", "no_ground_truth": True, "eligible_count": 0})
    s = scoring_model.score_financial_accuracy(inp, profile)
    assert s is None


@pytest.mark.offline
def test_compute_weighted_with_gt(profile):
    result = scoring_model.compute(_inputs(), profile)
    assert "weighted_score" in result
    assert 0.0 <= result["weighted_score"] <= 10.0
    assert result["dimensions"]["financial_accuracy"] is not None
    assert result["weighting_note"] == ""
    assert result["level"] in {"good", "fair", "poor"}


@pytest.mark.offline
def test_compute_emits_score_sources(profile):
    """score_result 必须携带 score_sources（deterministic 列全维度，llm_judge 默认空）。"""
    result = scoring_model.compute(_inputs(), profile)
    sources = result.get("score_sources")
    assert isinstance(sources, dict)
    assert sources["llm_judge"] == []
    # deterministic 应覆盖全部确定性维度且与 dimensions 的 key 集一致。
    assert set(sources["deterministic"]) == set(result["dimensions"].keys())
    for dim in ("output_contract", "table_structure", "financial_accuracy", "cost_performance"):
        assert dim in sources["deterministic"]


@pytest.mark.offline
def test_compute_weighted_redistributes_when_no_gt(profile):
    inp = _inputs(gt_eval={"status": "no_ground_truth", "no_ground_truth": True, "eligible_count": 0})
    result = scoring_model.compute(inp, profile)
    assert result["dimensions"]["financial_accuracy"] is None
    assert result["weighting_note"], "missing weighting_note when accuracy unavailable"
    # The financial_accuracy weight (0.35) must be redistributed to other dims, so
    # the sum of (non-financial_accuracy) applied weights ≈ 1.0
    w = result["weights_applied"]
    assert "financial_accuracy" not in w
    s = sum(w.values())
    assert s == pytest.approx(1.0, abs=0.01), f"weights should sum to ~1.0, got {s}: {w}"


@pytest.mark.offline
def test_compute_cost_performance_status_failed(profile):
    inp = _inputs(run_meta={"page_count": 2, "status": "failed"})
    s = scoring_model.score_cost_performance(inp, profile)
    assert s == profile["cost_performance"]["status_failed"]


@pytest.mark.offline
def test_compute_cost_performance_page_buckets(profile):
    inp_small = _inputs(run_meta={"page_count": 5, "status": "success"})
    inp_large = _inputs(run_meta={"page_count": 200, "status": "success"})
    assert scoring_model.score_cost_performance(inp_small, profile) >= scoring_model.score_cost_performance(inp_large, profile)


@pytest.mark.offline
def test_abnormal_handling_expected_match(profile):
    case = {"case_id": "t", "expected_error": {"error_code": "FILE_NOT_FOUND"}, "tags": ["abnormal"]}
    assertions = [{"type": "error_type_eq", "passed": True, "message": "ok"}]
    inp = _inputs(case=case, assertions=assertions)
    assert scoring_model.score_abnormal_handling(inp, profile) == profile["abnormal_handling"]["expected_match"]


@pytest.mark.offline
def test_level_bands(profile):
    high = _inputs()
    result_high = scoring_model.compute(high, profile)
    assert result_high["level"] in {"good", "fair", "poor"}

    # Force every dimension to a low score by providing failing inputs.
    low_inputs = _inputs(
        quality_checks={"table_statistics": {"raw_table_count": 0, "financial_table_count": 0}, "data_authenticity": {"is_synthetic": True}},
        run_meta={"page_count": 200, "status": "failed"},
        assertions=[
            {"type": "output_contract", "passed": False, "message": "missing"},
            {"type": "data_authenticity", "passed": False, "message": "synth"},
        ],
        gt_eval=None,
    )
    result_low = scoring_model.compute(low_inputs, profile)
    assert result_low["weighted_score"] < result_high["weighted_score"]
    assert result_low["level"] == "poor"
