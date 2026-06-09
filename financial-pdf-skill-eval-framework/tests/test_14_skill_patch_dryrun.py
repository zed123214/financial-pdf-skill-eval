"""Offline coverage for optimizer.skill_patch (Step 4：propose + apply + snapshot + 校验)。"""
from __future__ import annotations

import json

import pytest

from optimizer import skill_patch

pytestmark = pytest.mark.offline


def _trace(targets):
    return {
        "case_id": "byd_real_las_fixture",
        "skill_version": "skill_v0_baseline",
        "failed_dimensions": [],
        "deterministic_failures": [],
        "judge_failures": [],
        "suggested_targets": targets,
    }


def test_propose_generates_patch_with_scope_and_relative_target(tmp_path, monkeypatch):
    """propose 从 failure_trace 生成 target_scope + 相对 target_file 的 patch。"""
    out_dir = tmp_path / "proposed"
    monkeypatch.setattr(skill_patch, "PROPOSED_DIR", out_dir)
    patches = skill_patch.propose_patches([_trace(["multi_header_table_rebuilder"])])
    assert len(patches) >= 1
    p = patches[0]
    assert p["patch_id"] == "patch_v1_multi_header"
    assert p["target_scope"] == "skill"
    assert p["target_file"] == "rules/multi_header_table_rebuilder.yaml"
    # 写盘成功。
    assert (out_dir / "patch_v1_multi_header.json").exists()


def test_proposed_patch_passes_schema_validation():
    patch = skill_patch._patch_for_target("multi_header_table_rebuilder")
    ok, errs = skill_patch.validate_patch(patch)
    assert ok, errs


def test_validate_rejects_absolute_and_dotdot_paths():
    bad_abs = {
        "patch_id": "bad_abs", "target_scope": "skill", "target_file": "/etc/passwd",
        "edit_type": "add", "reason": "x", "change": {},
    }
    bad_dotdot = {
        "patch_id": "bad_dotdot", "target_scope": "skill", "target_file": "../../evil.yaml",
        "edit_type": "add", "reason": "x", "change": {},
    }
    bad_scope = {
        "patch_id": "bad_scope", "target_scope": "framework", "target_file": "rules/x.yaml",
        "edit_type": "add", "reason": "x", "change": {},
    }
    assert not skill_patch.validate_patch(bad_abs)[0]
    assert not skill_patch.validate_patch(bad_dotdot)[0]
    assert not skill_patch.validate_patch(bad_scope)[0]


def test_apply_to_workspace_seeds_candidate_and_writes_rule(tmp_path):
    """apply 应从 baseline 复制 Skill 包到 candidate，并在其中写规则，不碰生产目录。"""
    candidate = tmp_path / "skill_candidate"
    patch = skill_patch._patch_for_target("multi_header_table_rebuilder")
    target = skill_patch.apply_to_workspace(patch, candidate)
    # candidate 是完整 Skill 包（含 SKILL.md），且规则写入 rules/ 下。
    assert (candidate / "SKILL.md").exists()
    assert target.exists()
    assert target.parent.name == "rules"
    assert candidate in target.parents
    # 生产 Skill 根目录未被写入该规则文件。
    prod_rule = skill_patch.SKILL_PKG_DIR / "rules" / "multi_header_table_rebuilder.yaml"
    assert not prod_rule.exists()


def test_judge_scope_apply_blocked_in_dry_run(tmp_path):
    candidate = tmp_path / "skill_candidate"
    judge_patch = {
        "patch_id": "patch_v1_judge", "target_scope": "judge",
        "target_file": "assessment_skill.md", "edit_type": "replace",
        "reason": "x", "change": {"text": "should not be written to production judge/"},
    }
    with pytest.raises(PermissionError):
        skill_patch.apply_to_workspace(judge_patch, candidate, allow_judge_apply=False)


def test_snapshot_version_copies_candidate(tmp_path, monkeypatch):
    candidate = tmp_path / "skill_candidate"
    patch = skill_patch._patch_for_target("multi_header_table_rebuilder")
    skill_patch.apply_to_workspace(patch, candidate)
    versions_dir = tmp_path / "skill_versions"
    monkeypatch.setattr(skill_patch, "SKILL_VERSIONS_DIR", versions_dir)
    dest = skill_patch.snapshot_version("unit_test", candidate)
    assert dest.exists()
    assert (dest / "SKILL.md").exists()
    assert (dest / "rules" / "multi_header_table_rebuilder.yaml").exists()
