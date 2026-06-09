"""用于测试用例验证的统一断言引擎。

每次检查返回：
  {type, passed, message, expected, actual}
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from framework import gt_evaluator, output_contract
from framework.context import FRAMEWORK_ROOT
from framework.logger import get_logger

LOG = get_logger("assertion_engine")


def _check(type_: str, passed: bool, message: str, expected: Any = None, actual: Any = None) -> dict:
    return {"type": type_, "passed": bool(passed), "message": message, "expected": expected, "actual": actual}


def _resolve(p: str | Path) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path
    return (FRAMEWORK_ROOT / path).resolve()


def _stat(qc: dict, meta: dict, field: str) -> int | None:
    table_stats = qc.get("table_statistics") or {}
    metric_stats = qc.get("metric_statistics") or {}
    if field in table_stats:
        return table_stats[field]
    if field in metric_stats:
        return metric_stats[field]
    if field in meta:
        return meta[field]
    return None


def run_validations(case: dict, invocation: dict) -> list[dict]:
    results: list[dict] = []
    validations = case.get("validations") or []
    output_dir_str = invocation.get("output_dir") or case.get("output_dir")
    if not output_dir_str:
        results.append(_check("internal", False, "no output_dir resolved"))
        return results
    output_dir = _resolve(output_dir_str)

    meta = output_contract.read_run_meta(output_dir)
    qc = output_contract.read_quality_checks(output_dir)

    for v in validations:
        vtype = v.get("type")
        try:
            if vtype == "output_contract":
                profile = v.get("profile", case.get("output_profile", "standard"))
                res = output_contract.validate_standard_output(output_dir, profile)
                results.append(_check("output_contract", res.get("passed", False), res.get("message", ""), expected=profile, actual=res.get("missing_files", [])))

            elif vtype == "data_authenticity":
                expected_backend = v.get("expected_backend")
                require_non_synthetic = v.get("require_non_synthetic", False)
                allow_synthetic = v.get("allow_synthetic", True)
                auth = qc.get("data_authenticity") or {}
                eb = auth.get("execution_backend") or meta.get("execution_backend")
                is_synth = auth.get("is_synthetic", meta.get("is_synthetic"))
                ok = True
                msgs = []
                if expected_backend and eb != expected_backend:
                    ok = False
                    msgs.append(f"execution_backend {eb} != {expected_backend}")
                if require_non_synthetic and is_synth:
                    ok = False
                    msgs.append("is_synthetic=true but case requires non-synthetic")
                if not allow_synthetic and is_synth:
                    ok = False
                    msgs.append("is_synthetic=true not allowed")
                results.append(_check("data_authenticity", ok, ";".join(msgs) or "authenticity ok", expected=expected_backend, actual={"execution_backend": eb, "is_synthetic": is_synth}))

            elif vtype in {"table_stat_ge", "table_stat_eq", "metric_stat_ge", "metric_stat_eq"}:
                field = v.get("field")
                expected = v.get("expected")
                actual = _stat(qc, meta, field)
                if actual is None:
                    results.append(_check(vtype, False, f"field {field} missing in quality_checks/run_meta", expected, None))
                    continue
                if vtype.endswith("_ge"):
                    passed = actual >= expected
                else:
                    passed = actual == expected
                results.append(_check(vtype, passed, f"{field}={actual} (expected {('>=' if vtype.endswith('_ge') else '==')} {expected})", expected, actual))

            elif vtype in {"gt_exact_match_accuracy_ge", "gt_numeric_accuracy_ge"}:
                threshold = v.get("threshold", 0.0)
                skip_if_no_gt = v.get("skip_if_no_ground_truth", True)
                gt_path = case.get("ground_truth")
                gt = gt_evaluator.evaluate(output_dir, gt_path)
                if gt.get("no_ground_truth"):
                    if skip_if_no_gt:
                        results.append(_check(vtype, True, "skipped: no ground truth available", threshold, gt.get("reason")))
                    else:
                        results.append(_check(vtype, False, "ground truth required but missing", threshold, gt.get("reason")))
                    continue
                if gt.get("status") != "success":
                    results.append(_check(vtype, False, f"gt eval failed: {gt.get('reason')}", threshold, gt))
                    continue
                key = "exact_match_accuracy" if vtype.startswith("gt_exact") else "numeric_accuracy"
                actual = gt.get(key) or 0.0
                results.append(_check(vtype, actual >= threshold, f"{key}={actual} (>= {threshold})", threshold, actual))

            elif vtype == "backend_eq":
                expected = v.get("expected")
                actual = meta.get("execution_backend")
                results.append(_check(vtype, actual == expected, f"execution_backend={actual}", expected, actual))

            elif vtype == "error_type_eq":
                expected = v.get("expected")
                err = output_contract._read_json(output_dir / "meta" / "error_result.json", {})
                actual = err.get("error_code") if isinstance(err, dict) else None
                results.append(_check(vtype, actual == expected, f"error_code={actual}", expected, actual))

            elif vtype == "file_exists":
                rel = v.get("path")
                p = output_dir / rel
                results.append(_check(vtype, p.exists(), f"{rel} {'exists' if p.exists() else 'missing'}", rel, str(p)))

            elif vtype == "text_contains":
                rel = v.get("path")
                needle = v.get("text", "")
                p = output_dir / rel
                if not p.exists():
                    results.append(_check(vtype, False, f"{rel} missing", needle, None))
                    continue
                text = p.read_text(encoding="utf-8", errors="replace")
                results.append(_check(vtype, needle in text, f"{rel} contains needle={needle in text}", needle, None))

            elif vtype == "no_ground_truth_allowed":
                gt_path = case.get("ground_truth")
                gt = gt_evaluator.evaluate(output_dir, gt_path)
                results.append(_check(vtype, gt.get("no_ground_truth", False), gt.get("reason", ""), True, gt.get("no_ground_truth")))

            else:
                results.append(_check(vtype or "unknown", False, f"unknown validation type: {vtype}"))
        except Exception as e:
            results.append(_check(vtype or "unknown", False, f"validation crashed: {e}"))

    return results
