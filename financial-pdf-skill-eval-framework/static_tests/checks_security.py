"""扫描仓库内是否泄露 API Key / 绝对 Windows 路径等。

扫描范围：``financial-pdf-skill-eval-framework/`` 本身（不含 outputs / data /
.understand-anything / reports / .git）。

规则：
 - 命中 ``LAS_API_KEY=`` / ``ARK_API_KEY=`` / ``sk-`` / ``C:\\Users\\``
   且**不属于** ``.env.example`` 占位符（值为空或注释行）→ fail。
 - 单文件命中数会累加到 ``checks[i].hits``，便于排查。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from framework.context import FRAMEWORK_ROOT

# Patterns to flag.
KEY_PATTERNS = [
    re.compile(r"LAS_API_KEY\s*=\s*[^\s\"'#]+", re.IGNORECASE),
    re.compile(r"ARK_API_KEY\s*=\s*[^\s\"'#]+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
]
WIN_ABS_PATH = re.compile(r"C:\\\\Users\\\\")  # double escaped (in source); also detect literal
WIN_ABS_PATH_LITERAL = re.compile(r"C:\\Users\\")

EXCLUDE_DIRS = {
    ".git", ".understand-anything", ".idea", ".vscode", "__pycache__",
    "node_modules", "reports", "outputs",
    "data",  # outputs / fixtures may contain real paths
    "allure-results",
    ".venv", "venv", "env", ".tox", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "site-packages", "dist", "build", ".egg-info",
}

ALLOW_FILES = {
    ".env.example",  # placeholder env file
}


def _iter_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        # skip excluded directories
        if any(part in EXCLUDE_DIRS for part in p.relative_to(root).parts):
            continue
        if p.name in ALLOW_FILES:
            continue
        # skip binaries / large files
        if p.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".zip", ".lock", ".dll", ".pyc", ".exe", ".so", ".whl", ".bin"}:
            continue
        if p.stat().st_size > 512 * 1024:
            continue
        yield p


def _scan_text(text: str) -> dict[str, list[str]]:
    hits = {"api_key": [], "absolute_path": []}
    for pat in KEY_PATTERNS:
        for m in pat.finditer(text):
            value = m.group(0)
            # skip placeholders like `LAS_API_KEY=` (empty value) or in comments
            if value.endswith("=") or value.lower().endswith(("=changeme", "=your_key", "=xxx", "=placeholder")):
                continue
            hits["api_key"].append(value[:120])
    for m in WIN_ABS_PATH_LITERAL.finditer(text):
        hits["absolute_path"].append(m.group(0))
    return hits


def run(scan_root: Path | None = None) -> dict[str, Any]:
    root = scan_root or FRAMEWORK_ROOT
    findings: list[dict[str, Any]] = []
    api_key_hit = False
    abs_path_hit = False
    for p in _iter_files(root):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        # Skip files that are part of static_tests itself - those contain the patterns by design.
        rel = p.relative_to(root)
        if rel.parts and rel.parts[0] == "static_tests":
            continue
        hits = _scan_text(text)
        if hits["api_key"] or hits["absolute_path"]:
            findings.append({"path": str(rel), "hits": hits})
            if hits["api_key"]:
                api_key_hit = True
            if hits["absolute_path"]:
                abs_path_hit = True
    return {
        "name": "security_ok",
        "passed": not (api_key_hit or abs_path_hit),
        "no_secret_leak": not api_key_hit,
        "no_absolute_path": not abs_path_hit,
        "findings": findings,
    }
