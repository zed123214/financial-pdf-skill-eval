"""Project paths and config resolution.

The framework lives at <repo>/financial-pdf-skill-eval-framework. All paths in
this module are resolved relative to that root, so tests run identically from
the repo root, the framework root, or pytest's tmpdir.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = FRAMEWORK_ROOT.parent


def _resolve(p: str | Path) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path
    return (FRAMEWORK_ROOT / path).resolve()


@dataclass
class SkillConfig:
    name: str
    path: Path
    run_script: Path
    validate_script: Path
    gt_eval_script: Path
    evidence_script: Path
    final_report_script: Path


@dataclass
class FrameworkConfig:
    skill: SkillConfig
    output_profile: str = "standard"
    parse_mode: str = "detail"
    backend: str = "fixture"
    allow_real_las: bool = False
    allow_real_openclaw: bool = False
    paths: dict[str, Path] = field(default_factory=dict)


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_config(config_path: str | Path | None = None) -> FrameworkConfig:
    cfg_file = Path(config_path) if config_path else FRAMEWORK_ROOT / "configs" / "config.example.yaml"
    if not cfg_file.is_absolute():
        cfg_file = _resolve(cfg_file)
    data = _load_yaml(cfg_file)

    skill_raw = data.get("skill") or {}
    skill = SkillConfig(
        name=skill_raw.get("name", "financial-pdf-parse-doubao-eval"),
        path=_resolve(skill_raw.get("path", "../skills/financial-pdf-parse-doubao-eval")),
        run_script=_resolve(skill_raw.get("run_script", "../skills/financial-pdf-parse-doubao-eval/scripts/run_financial_parse.py")),
        validate_script=_resolve(skill_raw.get("validate_script", "../skills/financial-pdf-parse-doubao-eval/scripts/validate_outputs.py")),
        gt_eval_script=_resolve(skill_raw.get("gt_eval_script", "../skills/financial-pdf-parse-doubao-eval/scripts/evaluate_with_ground_truth.py")),
        evidence_script=_resolve(skill_raw.get("evidence_script", "../skills/financial-pdf-parse-doubao-eval/scripts/collect_openclaw_evidence.py")),
        final_report_script=_resolve(skill_raw.get("final_report_script", "../skills/financial-pdf-parse-doubao-eval/scripts/generate_final_project_report.py")),
    )

    # SkillOpt gate override: 若设置 SKILL_DIR_OVERRIDE，则把 Skill 包根目录及所有脚本
    # 路径重指向 candidate workspace（不修改 config.example.yaml）。供 optimizer.gate 临时使用。
    override = os.environ.get("SKILL_DIR_OVERRIDE")
    if override:
        sk = Path(override).resolve()
        skill.path = sk
        skill.run_script = sk / "scripts" / "run_financial_parse.py"
        skill.validate_script = sk / "scripts" / "validate_outputs.py"
        skill.gt_eval_script = sk / "scripts" / "evaluate_with_ground_truth.py"
        skill.evidence_script = sk / "scripts" / "collect_openclaw_evidence.py"
        skill.final_report_script = sk / "scripts" / "generate_final_project_report.py"

    default = data.get("default") or {}
    paths_raw = data.get("paths") or {}
    paths = {k: _resolve(v) for k, v in paths_raw.items()}

    return FrameworkConfig(
        skill=skill,
        output_profile=default.get("output_profile", "standard"),
        parse_mode=default.get("parse_mode", "detail"),
        backend=default.get("backend", "fixture"),
        allow_real_las=bool(default.get("allow_real_las", False)) or os.environ.get("ALLOW_REAL_LAS") == "1",
        allow_real_openclaw=bool(default.get("allow_real_openclaw", False)) or os.environ.get("ALLOW_REAL_OPENCLAW") == "1",
        paths=paths,
    )


def project_path(name: str, fallback: str) -> Path:
    cfg = load_config()
    return cfg.paths.get(name, _resolve(fallback))
