"""Skill output_profile validator coverage."""
from __future__ import annotations

import subprocess
import sys

import pytest

from framework.context import FRAMEWORK_ROOT, load_config
from framework.output_contract import validate_standard_output


def test_validate_outputs_help():
    cfg = load_config()
    proc = subprocess.run([sys.executable, str(cfg.skill.validate_script), "--help"], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0
    assert "minimal" in proc.stdout
    assert "standard" in proc.stdout
    assert "debug" in proc.stdout


@pytest.mark.fixture
@pytest.mark.offline
def test_standard_profile_validates_byd_fixture():
    fixture = FRAMEWORK_ROOT / "data" / "real_las_outputs" / "byd_caibao"
    if not fixture.exists():
        pytest.skip("BYD fixture not imported")
    res = validate_standard_output(fixture, "standard")
    assert res.get("passed"), res


def test_default_consumes_standard_profile_only():
    """Documented automation contract: framework consumes standard profile by default."""
    cfg = load_config()
    assert cfg.output_profile == "standard"
