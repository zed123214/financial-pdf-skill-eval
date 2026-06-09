"""OpenClaw evidence collection coverage."""
from __future__ import annotations

import subprocess
import sys

import pytest

from framework.context import FRAMEWORK_ROOT, load_config


@pytest.mark.openclaw
@pytest.mark.offline
def test_collect_openclaw_evidence_writes_log(tmp_path):
    cfg = load_config()
    script = cfg.skill.evidence_script
    if not script.exists():
        pytest.skip("evidence script missing")
    out = tmp_path / "openclaw_invocation_log.md"
    outputs_dir = FRAMEWORK_ROOT / "data" / "real_las_outputs"
    proc = subprocess.run(
        [sys.executable, str(script),
         "--skill-dir", str(cfg.skill.path),
         "--outputs-dir", str(outputs_dir),
         "--output", str(out)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, f"evidence script failed: {proc.stderr}"
    assert out.exists(), "evidence log not written"
    text = out.read_text(encoding="utf-8")
    # Even if the openclaw CLI is unavailable, the log should still be written.
    assert len(text) > 0


@pytest.mark.openclaw
@pytest.mark.offline
def test_evidence_log_via_run_cli_appends_disclaimer():
    """run.py --collect-openclaw-evidence must ensure the disclaimer is present."""
    rc = subprocess.call([sys.executable, str(FRAMEWORK_ROOT / "run.py"), "--collect-openclaw-evidence"], cwd=str(FRAMEWORK_ROOT))
    assert rc == 0
    out = FRAMEWORK_ROOT / "reports" / "markdown" / "openclaw_invocation_log.md"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "real_las" in text
    assert ("real_openclaw" in text and ("not" in text.lower() or "尚未" in text)), (
        "openclaw_invocation_log.md must clarify that real_las != real_openclaw and real_openclaw is unverified"
    )
