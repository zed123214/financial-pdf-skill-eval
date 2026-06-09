"""failure_trace —— SkillOpt 之前的结构化失败轨迹中间层（collect + analyze 合一）。

把确定性评分失败、Ground Truth 失配、Judge 诊断扣分汇聚为一个结构化 JSON，
供后续 SkillOpt 读取（本任务**不**实现 SkillOpt / patch / gate）。

输入（均可选，缺失即按空处理）：
    - evaluation/score_result.json
    - evaluation/judge_result.json   （judge.enabled=false 时不存在 -> judge_failures=[]）
    - evaluation/gt_eval_result.json
    - assertions（assertion_engine.run_validations 的返回值）

输出：reports/traces/<case_id>_failure_trace.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from framework.context import FRAMEWORK_ROOT
from framework.logger import get_logger

LOG = get_logger("failure_trace")

# 维度判失阈值。确定性维度为 1~10，Judge 维度为 0~1。
DETERMINISTIC_FAIL_THRESHOLD = 6.0
JUDGE_FAIL_THRESHOLD = 0.6

# Judge 维度 / 失败签名 -> 建议优化目标（SkillOpt handoff 用，仅命名信号）。
_TARGET_RULES = {
    "multi_header_not_recovered": "multi_header_table_rebuilder",
    "period_column_issue": "period_column_normalizer",
    "missing_metric": "metric_extraction_recall",
    "numeric_mismatch": "numeric_value_normalizer",
    "table_structure": "multi_header_table_rebuilder",
    "reading_order": "reading_order_resolver",
    "evidence_alignment": "evidence_aligner",
}


def _resolve(p: str | Path) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (FRAMEWORK_ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - corrupt artifact
        LOG.warning("failed to read %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# analyze helpers
# ---------------------------------------------------------------------------
def _failed_dimensions(score_result: dict[str, Any] | None, judge_result: dict[str, Any] | None) -> list[str]:
    failed: list[str] = []
    dims = (score_result or {}).get("dimensions") or {}
    for name, val in dims.items():
        if val is None:
            continue  # null（如无 GT 的 financial_accuracy）不算失败。
        try:
            if float(val) < DETERMINISTIC_FAIL_THRESHOLD:
                failed.append(name)
        except (TypeError, ValueError):
            continue
    if judge_result:
        judge_dims = {
            "reading_order": judge_result.get("reading_order_score"),
            "table_structure": judge_result.get("table_structure_score"),
            "evidence_alignment": judge_result.get("evidence_alignment_score"),
        }
        for name, val in judge_dims.items():
            if val is None:
                continue
            if float(val) < JUDGE_FAIL_THRESHOLD and name not in failed:
                failed.append(name)
    return failed


def _deterministic_failures(gt_eval_result: dict[str, Any] | None, assertions: list[dict] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in (gt_eval_result or {}).get("failed_items") or []:
        actual = item.get("actual")
        ftype = "missing_metric" if actual in (None, "", "-") else "numeric_mismatch"
        out.append({
            "type": ftype,
            "statement": item.get("statement"),
            "item": item.get("item"),
            "period": item.get("period"),
            "expected": item.get("expected"),
            "actual": actual,
        })
    for a in assertions or []:
        if a.get("passed"):
            continue
        out.append({
            "type": "assertion_failed",
            "assertion_type": a.get("type"),
            "message": a.get("message"),
            "expected": a.get("expected"),
            "actual": a.get("actual"),
        })
    return out


def _judge_failure_type(dimension: str, reason: str) -> str:
    text = (reason or "").lower()
    if "表头" in reason or "header" in text:
        return "multi_header_not_recovered"
    if "期间" in reason or "period" in text:
        return "period_column_issue"
    return f"{dimension}_deduction"


def _judge_failures(judge_result: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not judge_result:
        return []
    out: list[dict[str, Any]] = []
    for d in judge_result.get("deduction_items") or []:
        dimension = d.get("dimension") or ""
        reason = d.get("reason") or ""
        out.append({
            "type": _judge_failure_type(dimension, reason),
            "dimension": dimension,
            "table_id": d.get("evidence"),
            "reason": reason,
        })
    return out


def _suggested_targets(
    failed_dimensions: list[str],
    deterministic_failures: list[dict],
    judge_failures: list[dict],
) -> list[str]:
    signatures: list[str] = []
    signatures.extend(d.get("type", "") for d in deterministic_failures)
    signatures.extend(j.get("type", "") for j in judge_failures)
    signatures.extend(failed_dimensions)
    targets: list[str] = []
    for sig in signatures:
        target = _TARGET_RULES.get(sig)
        if target and target not in targets:
            targets.append(target)
    return targets


# ---------------------------------------------------------------------------
# collect + analyze (combined entrypoint)
# ---------------------------------------------------------------------------
def build_trace(
    case: dict[str, Any],
    *,
    score_result: dict[str, Any] | None = None,
    judge_result: dict[str, Any] | None = None,
    gt_eval_result: dict[str, Any] | None = None,
    assertions: list[dict] | None = None,
    skill_version: str = "skill_v0_baseline",
) -> dict[str, Any]:
    """从已读入的产物构造 failure_trace（纯函数，便于单测）。"""
    failed_dims = _failed_dimensions(score_result, judge_result)
    det_failures = _deterministic_failures(gt_eval_result, assertions)
    judge_fail = _judge_failures(judge_result)
    return {
        "case_id": case.get("case_id", ""),
        "skill_version": skill_version,
        "failed_dimensions": failed_dims,
        "deterministic_failures": det_failures,
        "judge_failures": judge_fail,
        "suggested_targets": _suggested_targets(failed_dims, det_failures, judge_fail),
    }


def write_trace(trace: dict[str, Any]) -> Path:
    case_id = trace.get("case_id") or "unknown"
    target = FRAMEWORK_ROOT / "reports" / "traces" / f"{case_id}_failure_trace.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def run_for_case(
    case: dict[str, Any],
    assertions: list[dict] | None = None,
    skill_version: str = "skill_v0_baseline",
) -> dict[str, Any]:
    """读 case output_dir 下的评测产物，构造并落盘 failure_trace。

    judge_result.json / gt_eval_result.json 缺失时按空处理（不报错）。
    返回 {"trace": ..., "trace_path": ...}。
    """
    out_dir_raw = case.get("output_dir")
    if not out_dir_raw:
        raise ValueError("case missing output_dir")
    eval_dir = _resolve(out_dir_raw) / "evaluation"

    score_result = _read_json(eval_dir / "score_result.json")
    judge_result = _read_json(eval_dir / "judge_result.json")
    gt_eval_result = _read_json(eval_dir / "gt_eval_result.json")

    trace = build_trace(
        case,
        score_result=score_result,
        judge_result=judge_result,
        gt_eval_result=gt_eval_result,
        assertions=assertions,
        skill_version=skill_version,
    )
    path = write_trace(trace)
    return {"trace": trace, "trace_path": str(path)}
