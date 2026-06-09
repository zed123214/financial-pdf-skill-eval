"""Abnormal-case error handling."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from framework.case_loader import load_abnormal_cases
from framework.context import FRAMEWORK_ROOT, load_config
from framework.gt_evaluator import evaluate


ABNORMAL_PATH = FRAMEWORK_ROOT / "testcases" / "pdf_cases" / "abnormal_cases.yaml"
ABNORMAL_CASES = load_abnormal_cases(ABNORMAL_PATH)
ABNORMAL_BY_ID = {c["case_id"]: c for c in ABNORMAL_CASES}


def _resolve(p):
    p = Path(p)
    return p if p.is_absolute() else (FRAMEWORK_ROOT / p).resolve()


def _run_skill(case) -> subprocess.CompletedProcess:
    cfg = load_config()
    output_dir = _resolve(case["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(cfg.skill.run_script),
        "--input", str(_resolve(case["input_pdf"])),
        "--parse-mode", case.get("parse_mode", "detail"),
        "--output-dir", str(output_dir),
        "--output-profile", case.get("output_profile", "standard"),
        "--backend", case["backend"],
        "--yes",
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=os.environ.copy())


def _expected_err(case):
    return (case.get("expected_error") or {}).get("error_code")


@pytest.mark.abnormal
@pytest.mark.offline
def test_missing_input_pdf():
    case = ABNORMAL_BY_ID["missing_input_pdf"]
    proc = _run_skill(case)
    err = _resolve(case["output_dir"]) / "meta" / "error_result.json"
    assert err.exists(), f"expected error_result.json. stdout={proc.stdout} stderr={proc.stderr}"
    data = json.loads(err.read_text(encoding="utf-8"))
    assert data.get("error_code") == _expected_err(case)


@pytest.mark.abnormal
@pytest.mark.offline
def test_invalid_file_type():
    case = ABNORMAL_BY_ID["invalid_file_type"]
    proc = _run_skill(case)
    err = _resolve(case["output_dir"]) / "meta" / "error_result.json"
    assert err.exists(), f"expected error_result.json. stdout={proc.stdout} stderr={proc.stderr}"
    data = json.loads(err.read_text(encoding="utf-8"))
    assert data.get("error_code") == _expected_err(case)


@pytest.mark.abnormal
@pytest.mark.offline
def test_missing_ground_truth_does_not_fail():
    case = ABNORMAL_BY_ID["missing_ground_truth"]
    res = evaluate(case["output_dir"], case.get("ground_truth"))
    # Missing GT file must produce no_ground_truth, NOT a hard failure.
    assert res.get("status") in {"no_ground_truth", "skipped"}, res
    assert res.get("no_ground_truth") is True


@pytest.mark.abnormal
@pytest.mark.real_las
def test_real_las_without_key_is_skipped_not_failed():
    """When LAS_API_KEY is missing or ALLOW_REAL_LAS != 1, the framework must skip — not fail."""
    if os.environ.get("LAS_API_KEY") and os.environ.get("ALLOW_REAL_LAS") == "1":
        pytest.skip("LAS credentials are set; skipping the opt-out check")
    from framework import skill_invoker
    case = ABNORMAL_BY_ID["real_las_missing_key"]
    # Force the absence even if env happens to be set
    saved = {k: os.environ.pop(k, None) for k in ("LAS_API_KEY", "ALLOW_REAL_LAS")}
    try:
        result = skill_invoker.invoke(case)
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
    assert result["status"] == "skipped", result
    assert "LAS_API_KEY" in (result.get("skip_reason") or "") or "ALLOW_REAL_LAS" in (result.get("skip_reason") or "")
