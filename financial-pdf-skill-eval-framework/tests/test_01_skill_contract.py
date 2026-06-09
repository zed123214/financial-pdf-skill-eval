"""Skill output contract documentation checks."""
from __future__ import annotations

from framework.context import load_config


def test_output_schema_exists():
    cfg = load_config()
    p = cfg.skill.path / "references" / "output_schema.md"
    assert p.exists(), f"output_schema.md missing: {p}"
    text = p.read_text(encoding="utf-8")
    assert "Automation Interface Contract" in text
    # standard profile required files defined
    for required in [
        "raw/parsed.md",
        "normalized/normalized_tables.json",
        "normalized/financial_summary.json",
        "evaluation/quality_checks.json",
        "meta/run_meta.json",
    ]:
        assert required in text, f"required path missing from schema doc: {required}"
    # debug is troubleshooting, minimal is display
    assert "troubleshooting" in text.lower() or "排错" in text or "debug" in text.lower()
    assert "display" in text.lower() or "展示" in text or "minimal" in text.lower()
