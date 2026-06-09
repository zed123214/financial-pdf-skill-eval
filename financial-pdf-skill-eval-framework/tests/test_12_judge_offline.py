"""Offline coverage for the Assessment-Skill Judge layer (mock / skip / disabled)."""
from __future__ import annotations

import json
import shutil

import pytest

from framework import case_loader, pipeline
from framework.context import FRAMEWORK_ROOT
from judge import llm_judge

pytestmark = pytest.mark.offline


def _case(tmp_path, case_id="byd_caibao"):
    out = tmp_path / case_id
    (out / "evaluation").mkdir(parents=True, exist_ok=True)
    return {"case_id": case_id, "output_dir": str(out)}, out


@pytest.mark.offline
def test_default_config_is_disabled():
    """默认 configs/judge.yaml 必须 enabled=false。"""
    config = llm_judge.load_judge_config()
    assert llm_judge.is_enabled(config) is False


@pytest.mark.offline
def test_disabled_does_not_write_judge_result(tmp_path):
    case, out = _case(tmp_path)
    outcome = llm_judge.run_for_case(case, {"enabled": False, "mode": "mock"})
    assert outcome["enabled"] is False
    assert outcome["mode"] == "disabled"
    assert outcome["judge_result"] is None
    assert outcome["judge_dimensions"] == []
    assert not (out / "evaluation" / "judge_result.json").exists()


@pytest.mark.offline
def test_mock_mode_writes_judge_result(tmp_path):
    case, out = _case(tmp_path)
    config = {
        "enabled": True,
        "mode": "mock",
        "mock_fixture": "judge/fixtures/byd_caibao_judge_mock.json",
        "judge_version": "assessment_skill_v1",
    }
    outcome = llm_judge.run_for_case(case, config)
    assert outcome["enabled"] is True
    assert outcome["mode"] == "mock"

    jr_path = out / "evaluation" / "judge_result.json"
    assert jr_path.exists()
    jr = json.loads(jr_path.read_text(encoding="utf-8"))
    assert jr["case_id"] == "byd_caibao"
    assert jr["mode"] == "mock"
    for field in ("reading_order_score", "table_structure_score", "evidence_alignment_score"):
        assert 0.0 <= jr[field] <= 1.0
    # 给了三个非空分，judged dimensions 应覆盖全部 Judge 维度。
    assert set(outcome["judge_dimensions"]) == set(llm_judge.JUDGE_DIMENSIONS)
    # Judge 不评 financial_accuracy / output_contract 等确定性维度。
    assert "financial_accuracy" not in outcome["judge_dimensions"]


@pytest.mark.offline
def test_skip_mode_writes_skipped_result(tmp_path):
    case, out = _case(tmp_path)
    outcome = llm_judge.run_for_case(case, {"enabled": True, "mode": "skip"})
    jr_path = out / "evaluation" / "judge_result.json"
    assert jr_path.exists()
    jr = json.loads(jr_path.read_text(encoding="utf-8"))
    assert jr["mode"] == "skipped"
    assert jr["reading_order_score"] is None
    # skipped 无非空分 -> 不贡献任何 llm_judge 维度。
    assert outcome["judge_dimensions"] == []


@pytest.mark.offline
def test_live_with_mocked_chat_writes_live_result(tmp_path, monkeypatch):
    """live 路径：mock HTTP，应写出 mode=live 且三维有分。"""
    monkeypatch.setenv("JUDGE_API_KEY", "test-key")
    case, out = _case(tmp_path, case_id="live_smoke")
    for rel in llm_judge.JUDGE_INPUT_FILES:
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"stub": true}', encoding="utf-8")

    mock_payload = {
        "reading_order_score": 0.8,
        "table_structure_score": 0.75,
        "evidence_alignment_score": 0.85,
        "deduction_items": [
            {
                "dimension": "table_structure",
                "reason": "test deduction",
                "evidence": "table_001",
            }
        ],
        "confidence": 0.7,
        "mode": "should_be_overwritten",
    }

    def _fake_chat(config, system, user):
        assert "live_smoke" in user
        assert "Assessment Skill" in system or "assessment" in system.lower()
        return json.dumps(mock_payload)

    monkeypatch.setattr(llm_judge, "_deepseek_chat", _fake_chat)

    config = {
        "enabled": True,
        "mode": "live",
        "judge_version": "assessment_skill_v1",
        "live": {"api_key_env": "JUDGE_API_KEY", "max_excerpt_chars": 100},
    }
    outcome = llm_judge.run_for_case(case, config)
    assert outcome["mode"] == "live"
    assert outcome["warning"] is None
    assert set(outcome["judge_dimensions"]) == set(llm_judge.JUDGE_DIMENSIONS)

    jr = json.loads((out / "evaluation" / "judge_result.json").read_text(encoding="utf-8"))
    assert jr["mode"] == "live"
    assert jr["case_id"] == "live_smoke"
    assert jr["reading_order_score"] == 0.8


@pytest.mark.offline
def test_parse_judge_json_strips_markdown_fence():
    raw = """```json
{"reading_order_score": 0.5, "table_structure_score": 0.5,
 "evidence_alignment_score": 0.5, "deduction_items": [], "confidence": 0.5, "mode": "x"}
```"""
    parsed = llm_judge._parse_judge_json(raw, "c1", "v1")
    assert parsed["mode"] == "live"
    assert parsed["case_id"] == "c1"


@pytest.mark.offline
def test_live_without_key_degrades_to_skipped(tmp_path, monkeypatch):
    monkeypatch.delenv("JUDGE_API_KEY", raising=False)
    case, out = _case(tmp_path)
    config = {
        "enabled": True,
        "mode": "live",
        "live": {"api_key_env": "JUDGE_API_KEY"},
    }
    outcome = llm_judge.run_for_case(case, config)
    jr = json.loads((out / "evaluation" / "judge_result.json").read_text(encoding="utf-8"))
    assert jr["mode"] == "skipped"
    assert outcome["warning"]
    assert outcome["judge_dimensions"] == []


@pytest.mark.offline
def test_pipeline_judge_enabled_appends_score_sources(tmp_path, monkeypatch):
    """enabled=true+mock：run_judge 成功，score_sources.llm_judge 被追加，
    且 weighted_score 不被重算（仅诊断信号）。"""
    fixture = FRAMEWORK_ROOT / "data" / "real_las_outputs" / "byd_caibao"
    if not fixture.exists():
        pytest.skip("BYD fixture not imported")
    sandbox = tmp_path / "byd_caibao"
    shutil.copytree(fixture, sandbox)

    enabled_config = {
        "enabled": True,
        "mode": "mock",
        "mock_fixture": "judge/fixtures/byd_caibao_judge_mock.json",
        "judge_version": "assessment_skill_v1",
    }
    monkeypatch.setattr(llm_judge, "load_judge_config", lambda *a, **k: enabled_config)

    case = case_loader.normalize_case({
        "case_id": "byd_judge_smoke",
        "backend": "fixture",
        "output_profile": "standard",
        "output_dir": str(sandbox),
        "ground_truth": "evaluation/ground_truth/byd_manual_gt.json",
        "validations": [{"type": "output_contract", "profile": "standard"}],
        "tags": ["offline"],
    })
    result = pipeline.run_pipeline(case, static_first=False)

    judge_stage = next(s for s in result.stages if s.name == "run_judge")
    assert judge_stage.status == "success"

    score = json.loads((sandbox / "evaluation" / "score_result.json").read_text(encoding="utf-8"))
    assert set(score["score_sources"]["llm_judge"]) == set(llm_judge.JUDGE_DIMENSIONS)
    # deterministic 维度未被 Judge 污染。
    assert "financial_accuracy" in score["score_sources"]["deterministic"]
    # weighted_score 由确定性维度决定，Judge 不重算（fixture 基线为 8.8）。
    assert score["weighted_score"] == 8.8
    assert (sandbox / "evaluation" / "judge_result.json").exists()
