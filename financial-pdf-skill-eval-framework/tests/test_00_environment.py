"""Environment / Skill-presence sanity checks."""
from __future__ import annotations

import subprocess
import sys

import pytest

from framework.context import load_config


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.mark.smoke
def test_skill_dir_exists(cfg):
    assert cfg.skill.path.exists(), f"Skill dir missing: {cfg.skill.path}"


def test_skill_md_exists(cfg):
    assert (cfg.skill.path / "SKILL.md").exists()


@pytest.mark.parametrize("attr", [
    "run_script", "validate_script", "gt_eval_script", "evidence_script", "final_report_script",
])
def test_skill_scripts_exist(cfg, attr):
    path = getattr(cfg.skill, attr)
    assert path.exists(), f"missing script: {path}"


def test_run_script_help_advertises_output_profile(cfg):
    proc = subprocess.run([sys.executable, str(cfg.skill.run_script), "--help"], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0
    assert "--output-profile" in proc.stdout


def test_validate_script_help_advertises_output_profile(cfg):
    proc = subprocess.run([sys.executable, str(cfg.skill.validate_script), "--help"], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0
    assert "--output-profile" in proc.stdout
