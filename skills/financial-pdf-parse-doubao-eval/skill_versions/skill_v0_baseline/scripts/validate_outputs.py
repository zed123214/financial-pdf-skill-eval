from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = Path(__file__).resolve().parents[1]

PROFILE_REQUIRED = {
    "minimal": [
        "parsed.md",
        "financial_summary.json",
        "evaluation_report.md",
        "run_meta.json",
    ],
    "standard": [
        "raw/parsed.md",
        "normalized/normalized_tables.json",
        "normalized/financial_summary.json",
        "evaluation/quality_checks.json",
        "evaluation/evaluation_report.md",
        "meta/run_meta.json",
    ],
    "debug": [
        "raw/result.json",
        "raw/parsed.md",
        "raw/pages_detail.json",
        "normalized/cleaned.md",
        "normalized/normalized_tables.json",
        "normalized/financial_summary.json",
        "evaluation/quality_checks.json",
        "evaluation/evaluation_report.md",
        "meta/run_meta.json",
    ],
}

DEBUG_OPTIONAL = [
    "raw/submit.json",
    "raw/raw_stdout.log",
    "raw/raw_stderr.log",
    "meta/error_result.json",
    "evaluation/gt_eval_result.json",
]

DEBUG_LEGACY_ALIASES = {
    "raw/result.json": ["result.json"],
    "raw/parsed.md": ["parsed.md"],
    "raw/pages_detail.json": ["pages_detail.json"],
    "normalized/cleaned.md": ["cleaned.md"],
    "normalized/normalized_tables.json": ["normalized_tables.json"],
    "normalized/financial_summary.json": ["financial_summary.json"],
    "evaluation/quality_checks.json": ["quality_checks.json", "eval_result.json"],
    "evaluation/evaluation_report.md": ["evaluation_report.md"],
    "meta/run_meta.json": ["run_meta.json"],
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def json_files(paths: list[str]) -> list[str]:
    return [path for path in paths if path.endswith(".json")]


def candidates(output_profile: str, relative: str) -> list[str]:
    if output_profile == "debug":
        return [relative] + DEBUG_LEGACY_ALIASES.get(relative, [])
    return [relative]


def first_existing(output_dir: Path, output_profile: str, relative: str) -> Path | None:
    for candidate in candidates(output_profile, relative):
        path = output_dir / candidate
        if path.is_file():
            return path
    return None


def validate(
    output_dir: Path,
    output_profile: str = "standard",
    keep_pages_detail: bool = False,
) -> dict[str, Any]:
    if output_profile not in PROFILE_REQUIRED:
        raise ValueError("output_profile must be minimal, standard, or debug")

    checked_files = list(PROFILE_REQUIRED[output_profile])
    if output_profile == "standard" and keep_pages_detail:
        checked_files.append("raw/pages_detail.json")

    missing_files = [relative for relative in checked_files if first_existing(output_dir, output_profile, relative) is None]
    invalid_json: list[dict[str, str]] = []
    for relative in json_files(checked_files):
        path = first_existing(output_dir, output_profile, relative)
        if path is None:
            continue
        try:
            load_json(path)
        except Exception as exc:
            invalid_json.append({"file": relative, "error": str(exc)})

    parsed_path = output_dir / "parsed.md" if output_profile == "minimal" else first_existing(output_dir, output_profile, "raw/parsed.md")
    parsed_non_empty = True
    if parsed_path and parsed_path.exists():
        parsed_non_empty = bool(parsed_path.read_text(encoding="utf-8", errors="ignore").strip())

    run_meta_path = output_dir / "run_meta.json" if output_profile == "minimal" else first_existing(output_dir, output_profile, "meta/run_meta.json")
    authenticity_ok = True
    authenticity_message = "not checked"
    if run_meta_path and run_meta_path.exists():
        try:
            meta = load_json(run_meta_path)
            authenticity_ok = not bool(meta.get("is_synthetic")) or not bool(meta.get("count_as_real_evaluation"))
            authenticity_message = "ok" if authenticity_ok else "synthetic output must not count as real evaluation"
        except Exception as exc:
            authenticity_ok = False
            authenticity_message = f"run_meta invalid: {exc}"

    passed = not missing_files and not invalid_json and parsed_non_empty and authenticity_ok
    message = (
        f"Output validation passed for {output_profile} profile."
        if passed
        else f"Output validation failed for {output_profile} profile."
    )
    result: dict[str, Any] = {
        "output_profile": output_profile,
        "passed": passed,
        "missing_files": missing_files,
        "checked_files": checked_files,
        "message": message,
    }
    if invalid_json:
        result["invalid_json"] = invalid_json
    if not parsed_non_empty:
        result["parsed_markdown_error"] = "parsed.md is empty"
    if not authenticity_ok:
        result["data_authenticity_error"] = authenticity_message
    if output_profile == "debug":
        result["optional_files_present"] = [relative for relative in DEBUG_OPTIONAL if (output_dir / relative).is_file()]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate financial PDF parse outputs by output profile.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/financial_skill_demo"))
    parser.add_argument("--output-profile", choices=["minimal", "standard", "debug"], default="standard")
    parser.add_argument("--keep-pages-detail", action="store_true")
    args = parser.parse_args()

    result = validate(args.output_dir, args.output_profile, args.keep_pages_detail)
    print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stdout if result["passed"] else sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
