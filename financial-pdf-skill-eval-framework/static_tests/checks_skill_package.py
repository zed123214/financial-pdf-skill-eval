"""检查被测 Skill 包的完整性（不调用 Skill，仅看文件是否存在）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from framework.context import load_config

REQUIRED_RELATIVE = [
    "SKILL.md",
    "_meta.json",
    "scripts/run_financial_parse.py",
    "scripts/validate_outputs.py",
    "scripts/evaluate_with_ground_truth.py",
]


def run() -> dict[str, Any]:
    cfg = load_config()
    base: Path = cfg.skill.path
    missing: list[str] = []
    present: list[str] = []
    for rel in REQUIRED_RELATIVE:
        p = base / rel
        if p.is_file():
            present.append(rel)
        else:
            missing.append(rel)
    return {
        "name": "skill_package_ok",
        "passed": not missing,
        "skill_path": str(base),
        "present": present,
        "missing": missing,
    }
