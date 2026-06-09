"""Offline coverage for optimizer.failure_trace (collect + analyze)."""
from __future__ import annotations

import json

import pytest

from optimizer import failure_trace

pytestmark = pytest.mark.offline


def _score_result(table_structure=8, financial_accuracy=None):
    return {
        "case_id": "byd_caibao",
        "dimensions": {
            "output_contract": 10,
            "data_authenticity": 10,
            "table_structure": table_structure,
            "financial_accuracy": financial_accuracy,
            "abnormal_handling": 8,
            "cost_performance": 10,
        },
        "weighted_score": 8.8,
        "score_sources": {"deterministic": ["table_structure"], "llm_judge": []},
    }


@pytest.mark.offline
def test_build_trace_no_judge_keeps_judge_failures_empty():
    """judge.enabled=false（无 judge_result）时 judge_failures 必须为空。"""
    trace = failure_trace.build_trace(
        {"case_id": "byd_caibao"},
        score_result=_score_result(),
        judge_result=None,
        gt_eval_result=None,
        assertions=[],
    )
    assert trace["case_id"] == "byd_caibao"
    assert trace["skill_version"] == "skill_v0_baseline"
    assert trace["judge_failures"] == []
    # table_structure=8 >= 阈值，不应进入 failed_dimensions。
    assert "table_structure" not in trace["failed_dimensions"]


@pytest.mark.offline
def test_build_trace_collects_deterministic_failures():
    gt_eval = {
        "failed_items": [
            {"statement": "合并资产负债表", "item": "资产总计", "period": "2025-12-31", "expected": "100", "actual": None},
            {"statement": "合并资产负债表", "item": "负债合计", "period": "2025-12-31", "expected": "50", "actual": "49"},
        ]
    }
    trace = failure_trace.build_trace(
        {"case_id": "byd_caibao"},
        score_result=_score_result(table_structure=3),
        gt_eval_result=gt_eval,
        assertions=[{"type": "output_contract", "passed": False, "message": "missing file"}],
    )
    types = {f["type"] for f in trace["deterministic_failures"]}
    assert "missing_metric" in types
    assert "numeric_mismatch" in types
    assert "assertion_failed" in types
    # table_structure=3 < 阈值 -> 进入 failed_dimensions。
    assert "table_structure" in trace["failed_dimensions"]


@pytest.mark.offline
def test_build_trace_with_judge_populates_judge_failures_and_targets():
    judge_result = {
        "reading_order_score": 0.85,
        "table_structure_score": 0.5,
        "evidence_alignment_score": 0.9,
        "deduction_items": [
            {"dimension": "table_structure", "reason": "多级表头未展开，period 列识别失败", "evidence": "table_6_1"},
        ],
    }
    trace = failure_trace.build_trace(
        {"case_id": "byd_caibao"},
        score_result=_score_result(),
        judge_result=judge_result,
        gt_eval_result={"failed_items": []},
        assertions=[],
    )
    assert len(trace["judge_failures"]) == 1
    jf = trace["judge_failures"][0]
    assert jf["type"] == "multi_header_not_recovered"
    assert jf["table_id"] == "table_6_1"
    # table_structure_score=0.5 < 0.6 -> judge 维度进入 failed_dimensions。
    assert "table_structure" in trace["failed_dimensions"]
    assert "multi_header_table_rebuilder" in trace["suggested_targets"]


@pytest.mark.offline
def test_run_for_case_writes_trace_file(tmp_path):
    eval_dir = tmp_path / "byd_caibao" / "evaluation"
    eval_dir.mkdir(parents=True)
    (eval_dir / "score_result.json").write_text(
        json.dumps(_score_result(table_structure=3), ensure_ascii=False), encoding="utf-8"
    )
    # judge_result.json / gt_eval_result.json 缺失 -> 应正常处理。
    case = {"case_id": "byd_caibao", "output_dir": str(tmp_path / "byd_caibao")}
    out = failure_trace.run_for_case(case, assertions=[])
    trace_path = out["trace_path"]
    assert trace_path.endswith("byd_caibao_failure_trace.json")
    written = json.loads(open(trace_path, encoding="utf-8").read())
    assert written["case_id"] == "byd_caibao"
    assert written["judge_failures"] == []
    assert "table_structure" in written["failed_dimensions"]
