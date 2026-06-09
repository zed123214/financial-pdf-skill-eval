"""扫描 case ``output_dir``，按 standard profile 列出必需 / 可选 artifact。

P0 中本模块仅做**只读**清点，不做语义校验（语义校验由
``framework.output_contract.validate_standard_output`` 负责）。返回结构供 pipeline
与 report 使用，例如：

```json
{
  "case_id": "byd_caibao",
  "output_dir": ".../byd_caibao",
  "artifacts": ["raw/parsed.md", "...", ...],
  "missing":   [],
  "optional_present": ["evaluation/evaluation_report.md"],
  "optional_missing": ["raw/result.json", "raw/pages_detail.json"],
  "artifact_ok": true
}
```
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from framework.context import FRAMEWORK_ROOT
from framework.logger import get_logger

LOG = get_logger("artifact_collector")


STANDARD_REQUIRED = [
    "raw/parsed.md",
    "normalized/normalized_tables.json",
    "normalized/financial_summary.json",
    "evaluation/quality_checks.json",
    "meta/run_meta.json",
]

STANDARD_OPTIONAL = [
    "evaluation/evaluation_report.md",
    "evaluation/gt_eval_result.json",
    "evaluation/score_result.json",
    "raw/result.json",
    "raw/pages_detail.json",
    "meta/error_result.json",
]


def _resolve(p: str | Path) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path
    return (FRAMEWORK_ROOT / path).resolve()


def collect(case: dict[str, Any], output_dir: str | Path | None = None) -> dict[str, Any]:
    """收集 case output_dir 下的 artifact。返回结构详见模块 docstring。"""
    case_id = case.get("case_id")
    od = output_dir or case.get("output_dir")
    if not od:
        return {
            "case_id": case_id,
            "output_dir": None,
            "artifacts": [],
            "missing": list(STANDARD_REQUIRED),
            "optional_present": [],
            "optional_missing": list(STANDARD_OPTIONAL),
            "artifact_ok": False,
            "reason": "case missing output_dir",
        }

    out = _resolve(od)
    artifacts: list[str] = []
    missing: list[str] = []
    if not out.exists():
        return {
            "case_id": case_id,
            "output_dir": str(out),
            "artifacts": [],
            "missing": list(STANDARD_REQUIRED),
            "optional_present": [],
            "optional_missing": list(STANDARD_OPTIONAL),
            "artifact_ok": False,
            "reason": f"output_dir not found: {out}",
        }

    for rel in STANDARD_REQUIRED:
        if (out / rel).is_file():
            artifacts.append(rel)
        else:
            missing.append(rel)

    optional_present: list[str] = []
    optional_missing: list[str] = []
    for rel in STANDARD_OPTIONAL:
        if (out / rel).is_file():
            optional_present.append(rel)
        else:
            optional_missing.append(rel)

    return {
        "case_id": case_id,
        "output_dir": str(out),
        "artifacts": artifacts,
        "missing": missing,
        "optional_present": optional_present,
        "optional_missing": optional_missing,
        "artifact_ok": not missing,
    }
