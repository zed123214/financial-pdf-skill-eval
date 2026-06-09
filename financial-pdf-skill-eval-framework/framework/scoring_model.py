"""P0 确定性评分模型。

输入：
 - quality_checks.json         (来自 case output_dir/evaluation/)
 - run_meta.json               (来自 case output_dir/meta/)
 - assertions                  (assertion_engine.run_validations 的返回值)
 - gt_eval_result              (gt_evaluator.evaluate 的返回值，可为 None / no_ground_truth)
 - scoring_profile yaml        (configs/scoring/pdf_financial_score.yaml)

输出（写入 case ``output_dir/evaluation/score_result.json``）：

```json
{
  "case_id": "byd_caibao",
  "profile": "pdf_financial_score",
  "dimensions": {
    "output_contract":     10,
    "data_authenticity":   10,
    "table_structure":      8,
    "financial_accuracy": null,
    "abnormal_handling":    8,
    "cost_performance":    10
  },
  "weights_applied": { ... },
  "weighted_score": 9.07,
  "level": "good",
  "weighting_note": "financial_accuracy unavailable, redistributed"
}
```

P0 中本模块为**纯函数**：所有需要的 JSON 都由调用方读好后传入，便于单元测试。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from framework.context import FRAMEWORK_ROOT
from framework.logger import get_logger

LOG = get_logger("scoring_model")

DEFAULT_PROFILE_PATH = FRAMEWORK_ROOT / "configs" / "scoring" / "pdf_financial_score.yaml"


@dataclass
class ScoreInputs:
    case_id: str
    quality_checks: dict[str, Any]
    run_meta: dict[str, Any]
    assertions: list[dict[str, Any]]
    gt_eval: dict[str, Any] | None
    case: dict[str, Any]


# ---------------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------------
def load_profile(profile_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(profile_path) if profile_path else DEFAULT_PROFILE_PATH
    if not path.is_absolute():
        path = (FRAMEWORK_ROOT / path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"scoring profile missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data


# ---------------------------------------------------------------------------
# Dimension scoring helpers
# ---------------------------------------------------------------------------
def _assertion_passed(assertions: list[dict], type_name: str) -> bool | None:
    """Return True/False if any assertion of given type exists; None if not present."""
    seen = False
    ok = True
    for a in assertions or []:
        if a.get("type") == type_name:
            seen = True
            if not a.get("passed"):
                ok = False
    return ok if seen else None


def score_output_contract(inputs: ScoreInputs, profile: dict) -> int:
    passed = _assertion_passed(inputs.assertions, "output_contract")
    if passed is None:
        # No explicit assertion - fall back to whether required files are present.
        required = [
            "raw/parsed.md", "normalized/normalized_tables.json",
            "normalized/financial_summary.json", "evaluation/quality_checks.json",
            "meta/run_meta.json",
        ]
        out_dir = inputs.case.get("output_dir")
        if not out_dir:
            return profile.get("severity_fail_score", {}).get("high", 2)
        out = Path(out_dir)
        if not out.is_absolute():
            out = (FRAMEWORK_ROOT / out).resolve()
        missing = [p for p in required if not (out / p).exists()]
        passed = not missing
    return profile["boolean_pass_score"] if passed else profile["severity_fail_score"]["high"]


def score_data_authenticity(inputs: ScoreInputs, profile: dict) -> int:
    passed = _assertion_passed(inputs.assertions, "data_authenticity")
    if passed is None:
        meta = inputs.run_meta or {}
        qc_auth = (inputs.quality_checks or {}).get("data_authenticity") or {}
        is_synth = qc_auth.get("is_synthetic", meta.get("is_synthetic", False))
        passed = not bool(is_synth)
    return profile["boolean_pass_score"] if passed else profile["severity_fail_score"]["critical"]


def score_table_structure(inputs: ScoreInputs, profile: dict) -> int:
    table_stats = (inputs.quality_checks or {}).get("table_statistics") or {}
    raw = int(table_stats.get("raw_table_count") or 0)
    fin = int(table_stats.get("financial_table_count") or 0)
    unknown = int(table_stats.get("unknown_table_count") or 0)
    cfg = profile.get("table_structure") or {}
    if raw == 0:
        return profile["severity_fail_score"]["high"]
    if fin == 0:
        return cfg.get("zero", 3)
    if fin >= 4 and unknown == 0:
        return cfg.get("excellent", 10)
    if fin >= 2:
        return cfg.get("good", 8)
    return cfg.get("partial", 6)


def score_financial_accuracy(inputs: ScoreInputs, profile: dict) -> int | None:
    gt = inputs.gt_eval or {}
    if not gt:
        return None
    if gt.get("no_ground_truth") or gt.get("status") in {"no_ground_truth", "skipped"}:
        return None
    if gt.get("status") == "failed":
        return profile["severity_fail_score"]["critical"]
    accuracy = gt.get("numeric_accuracy")
    eligible_count = gt.get("eligible_count")
    if eligible_count == 0 or accuracy is None:
        return None
    try:
        accuracy = float(accuracy)
    except (TypeError, ValueError):
        return None
    return round(1 + 9 * max(0.0, min(1.0, accuracy)), 1)


def score_abnormal_handling(inputs: ScoreInputs, profile: dict) -> int:
    cfg = profile.get("abnormal_handling") or {}
    case = inputs.case or {}
    expected_err = (case.get("expected_error") or {}).get("error_code")
    tags = case.get("tags") or []
    is_abnormal = "abnormal" in tags or bool(expected_err)
    if not is_abnormal:
        # 正常 case 不参与 abnormal 评分，给一个中性满分。
        return cfg.get("not_applicable", 8)
    # error_type_eq assertion is the canonical signal.
    matched = False
    for a in inputs.assertions or []:
        if a.get("type") == "error_type_eq" and a.get("passed"):
            matched = True
            break
        if a.get("type") == "no_ground_truth_allowed" and a.get("passed"):
            matched = True
            break
    return cfg.get("expected_match", 10) if matched else cfg.get("expected_miss", 3)


def score_cost_performance(inputs: ScoreInputs, profile: dict) -> int:
    cfg = profile.get("cost_performance") or {}
    meta = inputs.run_meta or {}
    status = meta.get("status") or "success"
    if status != "success":
        return cfg.get("status_failed", 1)
    pages = meta.get("page_count") or meta.get("input_page_count") or 0
    try:
        pages = int(pages)
    except (TypeError, ValueError):
        pages = 0
    for bucket in cfg.get("page_buckets") or []:
        if pages <= int(bucket["max_pages"]):
            return int(bucket["score"])
    return 4


# ---------------------------------------------------------------------------
# Weighting + final score
# ---------------------------------------------------------------------------
def _level_for(score: float, profile: dict) -> str:
    th = profile.get("level_thresholds") or {}
    if score >= float(th.get("good", 8.0)):
        return "good"
    if score >= float(th.get("fair", 6.0)):
        return "fair"
    return "poor"


def _apply_weights(dim_scores: dict[str, int | None], profile: dict) -> tuple[float, dict[str, float], str]:
    weights = dict(profile["weights"])
    note = ""
    if dim_scores.get("financial_accuracy") is None:
        # Redistribute the financial_accuracy weight per profile recipe.
        redist = profile.get("financial_accuracy_redistribute") or {}
        share = weights.pop("financial_accuracy", 0.0)
        if redist and share > 0:
            total = sum(float(v) for v in redist.values()) or 1.0
            for k, v in redist.items():
                weights[k] = weights.get(k, 0.0) + share * (float(v) / total)
            note = "financial_accuracy unavailable, redistributed"
        else:
            # Fallback: drop the weight and renormalize remaining weights to sum=1.
            remaining = sum(weights.values())
            if remaining > 0:
                weights = {k: v / remaining for k, v in weights.items()}
            note = "financial_accuracy unavailable, normalized remaining"
    # Compute weighted score, ignoring null dims.
    weighted = 0.0
    total_w = 0.0
    for k, w in weights.items():
        s = dim_scores.get(k)
        if s is None:
            continue
        weighted += float(s) * float(w)
        total_w += float(w)
    final = round(weighted / total_w, 2) if total_w > 0 else 0.0
    return final, weights, note


def compute(inputs: ScoreInputs, profile: dict | None = None) -> dict[str, Any]:
    profile = profile or load_profile()
    dim_scores: dict[str, int | None] = {
        "output_contract": score_output_contract(inputs, profile),
        "data_authenticity": score_data_authenticity(inputs, profile),
        "table_structure": score_table_structure(inputs, profile),
        "financial_accuracy": score_financial_accuracy(inputs, profile),
        "abnormal_handling": score_abnormal_handling(inputs, profile),
        "cost_performance": score_cost_performance(inputs, profile),
    }
    final, weights_applied, note = _apply_weights(dim_scores, profile)
    return {
        "case_id": inputs.case_id,
        "profile": profile.get("profile", "pdf_financial_score"),
        "dimensions": dim_scores,
        "weights_applied": {k: round(float(v), 4) for k, v in weights_applied.items()},
        "weighted_score": final,
        "level": _level_for(final, profile),
        "weighting_note": note,
        # 信号溯源：deterministic 列出参与 weighted_score 的确定性维度；
        # llm_judge 由可选 run_judge stage 追加（默认 []，不重算 weighted_score）。
        "score_sources": {
            "deterministic": list(dim_scores.keys()),
            "llm_judge": [],
        },
    }


def write_score_result(output_dir: str | Path, score_result: dict[str, Any]) -> Path:
    out = Path(output_dir)
    if not out.is_absolute():
        out = (FRAMEWORK_ROOT / out).resolve()
    target = out / "evaluation" / "score_result.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(score_result, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def compute_for_case(
    case: dict[str, Any],
    assertions: list[dict[str, Any]],
    gt_eval: dict[str, Any] | None,
    profile_path: str | Path | None = None,
) -> dict[str, Any]:
    """读 case output_dir 下的 JSON 并计算评分。该函数仅读盘，不写盘。"""
    from framework import output_contract  # local import to avoid cycle

    out_dir_raw = case.get("output_dir")
    if not out_dir_raw:
        raise ValueError("case missing output_dir")
    out_dir = Path(out_dir_raw)
    if not out_dir.is_absolute():
        out_dir = (FRAMEWORK_ROOT / out_dir).resolve()
    qc = output_contract.read_quality_checks(out_dir)
    meta = output_contract.read_run_meta(out_dir)
    profile = load_profile(profile_path) if profile_path else load_profile()
    inputs = ScoreInputs(
        case_id=case.get("case_id", ""),
        quality_checks=qc,
        run_meta=meta,
        assertions=assertions or [],
        gt_eval=gt_eval,
        case=case,
    )
    return compute(inputs, profile)
