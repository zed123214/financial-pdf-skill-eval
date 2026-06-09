"""扫描 ``evaluation/ground_truth/*.json``，校验最小结构 / source 信号。

P0 规则：
 - 每个文件都必须有 ``source`` 与 ``metrics``（list）；
 - ``source`` ∈ {manual, human_verified, manual_verified} 才允许参与准确率分母；
 - ``source == "todo_manual_verify"`` 且 ``metrics`` 全空 expected → ``warning``
   （不算 fail，避免与现有 BYD / Huadian / Pioneer 模板冲突）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from framework.context import FRAMEWORK_ROOT
from framework.gt_evaluator import MANUAL_SOURCES, _expected_filled

GT_DIR = FRAMEWORK_ROOT / "evaluation" / "ground_truth"


def run() -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    fail = False
    warnings: list[str] = []
    if not GT_DIR.exists():
        return {
            "name": "ground_truth_ok",
            "passed": False,
            "files": [],
            "message": f"GT dir not found: {GT_DIR}",
        }

    for jf in sorted(GT_DIR.glob("*.json")):
        entry: dict[str, Any] = {"path": str(jf.relative_to(FRAMEWORK_ROOT))}
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as e:
            entry["issues"] = [f"json parse error: {e}"]
            fail = True
            files.append(entry)
            continue
        if not isinstance(data, dict):
            entry["issues"] = ["root must be a JSON object"]
            fail = True
            files.append(entry)
            continue
        source = (data.get("source") or "").strip().lower()
        metrics = data.get("metrics", [])
        eligible = sum(1 for m in metrics if isinstance(m, dict) and _expected_filled(m))
        entry["source"] = source
        entry["metric_count"] = len(metrics) if isinstance(metrics, list) else 0
        entry["eligible_count"] = eligible
        entry["is_manual_source"] = source in MANUAL_SOURCES
        if "source" not in data:
            entry.setdefault("issues", []).append("missing field: source")
            fail = True
        if not isinstance(metrics, list):
            entry.setdefault("issues", []).append("metrics must be a list")
            fail = True
        # warn (not fail) when manual_verify slot is unfilled
        if source == "todo_manual_verify" and eligible == 0:
            warnings.append(f"{entry['path']} is a todo_manual_verify slot with empty expected")
        files.append(entry)

    return {
        "name": "ground_truth_ok",
        "passed": not fail,
        "warnings": warnings,
        "files": files,
    }
