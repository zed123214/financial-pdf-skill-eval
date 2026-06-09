"""校验 ``testcases/pdf_cases/*.yaml`` 的最小 schema。

P0 仅要求：
 - 每个单 case YAML 都有 ``case_id``、``backend``、``output_dir``；
 - 多 case 文件（``abnormal_cases.yaml`` 之类）每个子 case 也有上述字段；
 - 至少有 ``validations`` 列表（允许为空）。

不强制要求 ``validations`` 的具体 type 集，避免与已有 case 冲突。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from framework.context import FRAMEWORK_ROOT

CASES_DIR = FRAMEWORK_ROOT / "testcases" / "pdf_cases"

REQUIRED_FIELDS = ("case_id", "backend", "output_dir")


def _check_case_obj(obj: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for f in REQUIRED_FIELDS:
        if not obj.get(f):
            issues.append(f"missing field {f}")
    if "validations" in obj and not isinstance(obj.get("validations"), list):
        issues.append("validations must be a list when present")
    return issues


def run() -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    total_cases = 0
    total_issues = 0
    if not CASES_DIR.exists():
        return {
            "name": "case_schema_ok",
            "passed": False,
            "files": [],
            "message": f"cases dir not found: {CASES_DIR}",
        }

    for yml in sorted(CASES_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        except Exception as e:
            files.append({"path": str(yml), "issues": [f"yaml parse error: {e}"]})
            total_issues += 1
            continue
        issues: list[str] = []
        if isinstance(data, dict) and "cases" in data:
            for i, sub in enumerate(data.get("cases") or []):
                if not isinstance(sub, dict):
                    issues.append(f"cases[{i}] is not a mapping")
                    continue
                total_cases += 1
                sub_issues = _check_case_obj(sub)
                issues.extend([f"cases[{i}].{x}" for x in sub_issues])
        elif isinstance(data, dict):
            total_cases += 1
            issues.extend(_check_case_obj(data))
        else:
            issues.append("root must be a mapping or a {cases: [...]} document")
        files.append({"path": str(yml.relative_to(FRAMEWORK_ROOT)), "issues": issues})
        total_issues += len(issues)

    return {
        "name": "case_schema_ok",
        "passed": total_issues == 0,
        "files": files,
        "total_cases": total_cases,
        "total_issues": total_issues,
    }
