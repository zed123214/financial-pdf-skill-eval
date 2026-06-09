"""Optional allure attachment helper. No-op if allure-pytest is unavailable."""
from __future__ import annotations

from pathlib import Path

try:
    import allure  # type: ignore
    HAS_ALLURE = True
except Exception:
    HAS_ALLURE = False

STANDARD_ATTACHMENTS = [
    "raw/parsed.md",
    "normalized/normalized_tables.json",
    "normalized/financial_summary.json",
    "evaluation/quality_checks.json",
    "evaluation/evaluation_report.md",
    "evaluation/gt_eval_result.json",
    "meta/run_meta.json",
]


def attach_standard_outputs(output_dir: Path) -> None:
    if not HAS_ALLURE:
        return
    output_dir = Path(output_dir)
    for rel in STANDARD_ATTACHMENTS:
        p = output_dir / rel
        if not p.exists():
            continue
        try:
            if p.suffix == ".json":
                allure.attach(p.read_text(encoding="utf-8"), name=rel, attachment_type=allure.attachment_type.JSON)
            elif p.suffix == ".md":
                allure.attach(p.read_text(encoding="utf-8"), name=rel, attachment_type=allure.attachment_type.TEXT)
            else:
                allure.attach(p.read_bytes(), name=rel)
        except Exception:
            pass


def attach_invocation(invocation: dict) -> None:
    if not HAS_ALLURE or not invocation:
        return
    try:
        allure.attach(invocation.get("stdout", ""), name="invocation_stdout", attachment_type=allure.attachment_type.TEXT)
        allure.attach(invocation.get("stderr", ""), name="invocation_stderr", attachment_type=allure.attachment_type.TEXT)
        allure.attach(invocation.get("command", ""), name="invocation_command", attachment_type=allure.attachment_type.TEXT)
    except Exception:
        pass
