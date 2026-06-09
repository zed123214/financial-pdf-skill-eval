from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = Path(__file__).resolve().parents[1]


def normalize_number(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = text.replace(",", "").replace("，", "").replace(" ", "").replace("\u3000", "").replace("\xa0", "")
    if text in {"", "-", "－", "--", "—", "–"}:
        return ""
    negative = (text.startswith("(") and text.endswith(")")) or (text.startswith("（") and text.endswith("）"))
    if negative:
        text = text[1:-1]
    if negative and not text.startswith("-"):
        text = "-" + text
    return text


def normalize_period(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"（[^）]*）", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    return text


def decimal_value(value: Any) -> Decimal | None:
    normalized = normalize_number(value)
    if not normalized:
        return None
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def numeric_match(expected: Any, actual: Any) -> bool:
    left = decimal_value(expected)
    right = decimal_value(actual)
    if left is None or right is None:
        return normalize_number(expected) == normalize_number(actual)
    return abs(left - right) <= Decimal("0.01")


def reason_for_failure(expected: Any, actual: Any, found: bool) -> str:
    if not found:
        return "metric not found"
    expected_norm = normalize_number(expected)
    actual_norm = normalize_number(actual)
    if expected_norm.startswith("-") and actual_norm == expected_norm[1:]:
        return "negative sign lost"
    if "." in expected_norm and "." not in actual_norm:
        return "decimal point lost"
    return "value mismatch"


def metric_key(metric: dict[str, Any], period_normalized: bool = False) -> tuple[str, str, str]:
    period = normalize_period(metric.get("period", "")) if period_normalized else str(metric.get("period", "")).strip()
    return (
        str(metric.get("statement", "")).strip(),
        str(metric.get("item", "")).strip(),
        period,
    )


def index_actual_metrics(metrics: list[dict[str, Any]]) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]]]:
    exact: dict[tuple[str, str, str], dict[str, Any]] = {}
    normalized: dict[tuple[str, str, str], dict[str, Any]] = {}
    for metric in metrics:
        exact.setdefault(metric_key(metric, False), metric)
        normalized.setdefault(metric_key(metric, True), metric)
    return exact, normalized


def evaluate(financial_summary: dict[str, Any], ground_truth: dict[str, Any]) -> dict[str, Any]:
    actual_metrics = financial_summary.get("metrics", [])
    expected_metrics = ground_truth.get("metrics", [])
    exact_index, normalized_index = index_actual_metrics(actual_metrics)

    failed_items: list[dict[str, Any]] = []
    matched = 0
    numeric_matched = 0

    for expected in expected_metrics:
        actual = exact_index.get(metric_key(expected, False))
        if actual is None:
            actual = normalized_index.get(metric_key(expected, True))
        found = actual is not None
        actual_value = actual.get("value", "") if actual else ""
        expected_value = expected.get("expected", "")
        exact = found and str(actual_value).strip() == str(expected_value).strip()
        numeric = found and numeric_match(expected_value, actual_value)
        if exact:
            matched += 1
        if numeric:
            numeric_matched += 1
        if not exact or not numeric:
            failed_items.append(
                {
                    "statement": expected.get("statement", ""),
                    "item": expected.get("item", ""),
                    "period": expected.get("period", ""),
                    "expected": expected_value,
                    "actual": actual_value,
                    "exact_match": exact,
                    "numeric_match": numeric,
                    "reason": reason_for_failure(expected_value, actual_value, found),
                }
            )

    total = len(expected_metrics)
    return {
        "case_id": ground_truth.get("case_id", ""),
        "ground_truth_source": ground_truth.get("source", ""),
        "total": total,
        "matched": matched,
        "exact_match_accuracy": round(matched / total, 4) if total else 0.0,
        "numeric_accuracy": round(numeric_matched / total, 4) if total else 0.0,
        "failed_items": failed_items,
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def evaluate_files(financial_summary: Path, ground_truth: Path, output: Path) -> dict[str, Any]:
    result = evaluate(load_json(financial_summary), load_json(ground_truth))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate financial_summary.json against human Ground Truth.")
    parser.add_argument("--financial-summary", required=True, type=Path)
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = evaluate_files(args.financial_summary, args.ground_truth, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "message": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
