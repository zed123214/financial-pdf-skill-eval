"""调用 financial-pdf-parse-doubao-eval 技能 (Skill)。

后端语义 (Backend semantics)：
- fixture：不调用技能；该测试用例指向一个预先存在的 real_las 输出。
- official_output_mock：使用 --backend official_output_mock --mock-dir 参数调用该技能。
- real_las：使用 --backend real_las 参数调用该技能；受 LAS_API_KEY 和 ALLOW_REAL_LAS=1 环境变量的控制/限制。
- real_openclaw：默认跳过；未体验证。
invoke : 调用
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from framework.context import FRAMEWORK_ROOT, load_config
from framework.logger import get_logger

LOG = get_logger("skill_invoker")


class InvocationResult(dict):
    pass


def _resolve(p: str | Path) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path
    return (FRAMEWORK_ROOT / path).resolve()


def _skipped(case_id: str, backend: str, reason: str, command: str = "") -> InvocationResult:
    return InvocationResult({
        "case_id": case_id,
        "backend": backend,
        "status": "skipped",
        "skip_reason": reason,
        "command": command,
        "return_code": None,
        "stdout": "",
        "stderr": "",
        "output_dir": None,
        "duration_seconds": 0.0,
    })


def _success_no_run(case_id: str, backend: str, output_dir: Path) -> InvocationResult:
    return InvocationResult({
        "case_id": case_id,
        "backend": backend,
        "status": "success",
        "skip_reason": None,
        "command": "",
        "return_code": 0,
        "stdout": "",
        "stderr": "",
        "output_dir": str(output_dir),
        "duration_seconds": 0.0,
    })


def invoke(case: dict, *, dry_run: bool = False) -> InvocationResult:
    cfg = load_config()
    backend = case.get("backend") or cfg.backend
    case_id = case["case_id"]

    if backend == "fixture":
        output_dir = _resolve(case["output_dir"])
        if not output_dir.exists():
            return InvocationResult({
                "case_id": case_id,
                "backend": backend,
                "status": "failed",
                "skip_reason": None,
                "command": "",
                "return_code": 1,
                "stdout": "",
                "stderr": f"fixture output_dir does not exist: {output_dir}",
                "output_dir": str(output_dir),
                "duration_seconds": 0.0,
            })
        return _success_no_run(case_id, backend, output_dir)

    if backend == "real_openclaw":
        if not cfg.allow_real_openclaw:
            return _skipped(case_id, backend, "real_openclaw is unverified; set ALLOW_REAL_OPENCLAW=1 to opt in")
        return _skipped(case_id, backend, "real_openclaw backend not implemented yet")

    if backend == "real_las":
        if not os.environ.get("LAS_API_KEY"):
            return _skipped(case_id, backend, "LAS_API_KEY not set")
        if os.environ.get("ALLOW_REAL_LAS") != "1" and not cfg.allow_real_las:
            return _skipped(case_id, backend, "ALLOW_REAL_LAS != 1; real_las disabled to avoid cost")

    # build CLI for official_output_mock or real_las
    output_dir = _resolve(case["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    input_pdf = case.get("input_pdf")
    if not input_pdf:
        return InvocationResult({
            "case_id": case_id,
            "backend": backend,
            "status": "failed",
            "skip_reason": None,
            "command": "",
            "return_code": 2,
            "stdout": "",
            "stderr": "case missing input_pdf",
            "output_dir": str(output_dir),
            "duration_seconds": 0.0,
        })
    input_pdf_path = _resolve(input_pdf)
    parse_mode = case.get("parse_mode", cfg.parse_mode)
    output_profile = case.get("output_profile", cfg.output_profile)

    cmd: list[str] = [
        sys.executable,
        str(cfg.skill.run_script),
        "--input", str(input_pdf_path),
        "--parse-mode", parse_mode,
        "--output-dir", str(output_dir),
        "--output-profile", output_profile,
        "--backend", backend,
        "--yes",
    ]
    if case.get("keep_pages_detail"):
        cmd.append("--keep-pages-detail")
    if backend == "official_output_mock":
        mock_dir = case.get("mock_dir")
        if mock_dir:
            cmd.extend(["--mock-dir", str(_resolve(mock_dir))])

    command_str = " ".join(shlex.quote(c) for c in cmd)
    LOG.info("invoking skill: %s", command_str)

    if dry_run:
        return InvocationResult({
            "case_id": case_id,
            "backend": backend,
            "status": "dry_run",
            "skip_reason": None,
            "command": command_str,
            "return_code": None,
            "stdout": "",
            "stderr": "",
            "output_dir": str(output_dir),
            "duration_seconds": 0.0,
        })

    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=900)
        stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        stdout, stderr, rc = e.stdout or "", e.stderr or "", 124
    except Exception as e:
        stdout, stderr, rc = "", f"invocation error: {e}", 1
    duration = time.time() - t0

    status = "success" if rc == 0 else "failed"
    return InvocationResult({
        "case_id": case_id,
        "backend": backend,
        "status": status,
        "skip_reason": None,
        "command": command_str,
        "return_code": rc,
        "stdout": stdout,
        "stderr": stderr,
        "output_dir": str(output_dir),
        "duration_seconds": round(duration, 3),
    })
