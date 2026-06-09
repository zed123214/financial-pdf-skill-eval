"""Offline coverage for optimizer.gate (Step 5：validation + regression 门禁 + 路径覆盖)。"""
from __future__ import annotations

import json
import os

import pytest

from framework.context import load_config
from optimizer import gate, skill_patch

pytestmark = pytest.mark.offline


BYD_YAML = "testcases/pdf_cases/byd_real_las_fixture.yaml"


def _baseline(weighted=8.8):
    return {
        "skill_version": "skill_v0_baseline",
        "cases": [
            {
                "case_id": "byd_real_las_fixture",
                "weighted_score": weighted,
                "dimensions": {
                    "output_contract": 10, "data_authenticity": 10, "table_structure": 8,
                    "financial_accuracy": None, "abnormal_handling": 8, "cost_performance": 10,
                },
            }
        ],
    }


def _config(validation=None, regression=None):
    return {
        "splits": {
            "train": [BYD_YAML],
            "validation": validation if validation is not None else [],
            "regression": regression if regression is not None else [BYD_YAML],
        },
        "gate": {
            "require_output_contract_pass": True,
            "require_data_authenticity_pass": True,
            "min_weighted_score_vs_baseline": 0.0,
            "min_numeric_accuracy_vs_baseline": 0.0,
            "require_no_abnormal_regression": True,
            "require_improvement_on": [],
        },
        "patch": {"dry_run_only": True, "baseline_version": "skill_v0_baseline"},
    }


def _good_patch():
    return skill_patch._patch_for_target("multi_header_table_rebuilder")


# ---------------------------------------------------------------------------
# 路径覆盖：SKILL_DIR_OVERRIDE 必须生效，且指向 candidate 而非生产目录。
# ---------------------------------------------------------------------------
def test_skill_dir_override_resolves_to_candidate(tmp_path):
    candidate = skill_patch.ensure_candidate_workspace(tmp_path / "skill_candidate")
    marker = "SKILLOPT_TEST_MARKER_UNIQUE_42"
    skill_md = candidate / "SKILL.md"
    skill_md.write_text(skill_md.read_text(encoding="utf-8") + f"\n<!-- {marker} -->\n", encoding="utf-8")

    prev = os.environ.get("SKILL_DIR_OVERRIDE")
    os.environ["SKILL_DIR_OVERRIDE"] = str(candidate.resolve())
    try:
        cfg = load_config()
        assert cfg.skill.path == candidate.resolve()
        assert cfg.skill.path != skill_patch.SKILL_PKG_DIR.resolve()
        assert cfg.skill.run_script == candidate.resolve() / "scripts" / "run_financial_parse.py"
        assert marker in (cfg.skill.path / "SKILL.md").read_text(encoding="utf-8")
    finally:
        if prev is None:
            os.environ.pop("SKILL_DIR_OVERRIDE", None)
        else:
            os.environ["SKILL_DIR_OVERRIDE"] = prev
    # gate 运行后环境必须被清除，不污染后续 run.py。
    assert os.environ.get("SKILL_DIR_OVERRIDE") == prev


# ---------------------------------------------------------------------------
# accept：no_regression_accepted。
# ---------------------------------------------------------------------------
def test_gate_accepts_no_regression(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "OPT_DIR", tmp_path / "opt")
    monkeypatch.setattr(gate, "SCORE_DIFF_PATH", tmp_path / "opt" / "score_diff_v0_v1.json")
    result = gate.run_gate(
        _good_patch(),
        skillopt_config=_config(),
        baseline_summary=_baseline(),
        workspace_root=tmp_path / "skill_candidate",
    )
    assert result["accepted"] is True
    assert result["accept_type"] == "no_regression_accepted"
    assert result["evaluation_mode"] == "fixture_scores_only"
    assert result["skill_dir_used"].endswith("skill_candidate")
    assert skill_patch.SKILL_PKG_DIR.name not in os.path.basename(result["skill_dir_used"])
    assert result["validation_status"] == "skipped_no_cases"
    assert result["score_diff"]["byd_real_las_fixture"]["candidate"] == 8.8
    # 环境变量已恢复（无残留）。
    assert "SKILL_DIR_OVERRIDE" not in os.environ
    # score_diff 落盘。
    assert (tmp_path / "opt" / "score_diff_v0_v1.json").exists()


# ---------------------------------------------------------------------------
# reject：故意坏 patch（白名单失败）。
# ---------------------------------------------------------------------------
def test_gate_rejects_bad_patch(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REJECTED_BUFFER", tmp_path / "rejected_patch_buffer.json")
    monkeypatch.setattr(gate, "OPT_DIR", tmp_path / "opt")
    monkeypatch.setattr(gate, "SCORE_DIFF_PATH", tmp_path / "opt" / "score_diff_v0_v1.json")
    bad = {
        "patch_id": "patch_v1_bad", "target_scope": "skill",
        "target_file": "../../framework/scoring_model.py", "edit_type": "replace",
        "reason": "试图改评测器提分", "change": {"text": "evil"},
    }
    result = gate.run_gate(bad, skillopt_config=_config(), baseline_summary=_baseline(),
                           workspace_root=tmp_path / "skill_candidate")
    assert result["accepted"] is False
    assert result["accept_type"] == "rejected"
    assert result["reasons"]
    buf = json.loads((tmp_path / "rejected_patch_buffer.json").read_text(encoding="utf-8"))
    assert any(b["patch_id"] == "patch_v1_bad" for b in buf)


# ---------------------------------------------------------------------------
# regression：candidate 分数低于 baseline 时必须 reject。
# ---------------------------------------------------------------------------
def test_gate_rejects_on_weighted_regression(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REJECTED_BUFFER", tmp_path / "rejected_patch_buffer.json")
    monkeypatch.setattr(gate, "OPT_DIR", tmp_path / "opt")
    monkeypatch.setattr(gate, "SCORE_DIFF_PATH", tmp_path / "opt" / "score_diff_v0_v1.json")
    # baseline 人为抬高到 9.5 > candidate 实跑的 8.8 -> 视为回归。
    result = gate.run_gate(_good_patch(), skillopt_config=_config(), baseline_summary=_baseline(weighted=9.5),
                           workspace_root=tmp_path / "skill_candidate")
    assert result["accepted"] is False
    assert any("regressed" in r for r in result["reasons"])


# ---------------------------------------------------------------------------
# missing case：缺 yaml / 缺 fixture 不崩溃，写入 missing_cases。
# ---------------------------------------------------------------------------
def test_gate_records_missing_cases(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "OPT_DIR", tmp_path / "opt")
    monkeypatch.setattr(gate, "SCORE_DIFF_PATH", tmp_path / "opt" / "score_diff_v0_v1.json")
    cfg = _config(regression=[BYD_YAML, "testcases/pdf_cases/does_not_exist.yaml"])
    result = gate.run_gate(_good_patch(), skillopt_config=cfg, baseline_summary=_baseline(),
                           workspace_root=tmp_path / "skill_candidate")
    reasons = [m["reason"] for m in result["missing_cases"]]
    assert "yaml_missing" in reasons
    # byd 仍跑通，gate 不崩溃。
    assert "byd_real_las_fixture" in result["resolved_splits"]["regression"]


# ---------------------------------------------------------------------------
# validation 为空 -> skipped_no_cases，不宣称泛化提升。
# ---------------------------------------------------------------------------
def test_validation_skipped_no_cases(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "OPT_DIR", tmp_path / "opt")
    monkeypatch.setattr(gate, "SCORE_DIFF_PATH", tmp_path / "opt" / "score_diff_v0_v1.json")
    result = gate.run_gate(_good_patch(), skillopt_config=_config(validation=[]),
                           baseline_summary=_baseline(), workspace_root=tmp_path / "skill_candidate")
    assert result["validation_status"] == "skipped_no_cases"
