"""Validate real_las output fixtures under data/real_las_outputs/."""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.context import FRAMEWORK_ROOT
from framework.output_contract import (
    read_quality_checks,
    read_run_meta,
    validate_standard_output,
)


REAL_LAS_DIR = FRAMEWORK_ROOT / "data" / "real_las_outputs"


def _discover_fixtures() -> list[Path]:
    if not REAL_LAS_DIR.exists():
        return []
    out = []
    for sub in sorted(REAL_LAS_DIR.iterdir()):
        if sub.is_dir() and (sub / "meta" / "run_meta.json").exists():
            out.append(sub)
    return out


FIXTURES = _discover_fixtures()
FIXTURE_IDS = [f.name for f in FIXTURES]


if not FIXTURES:
    pytestmark = pytest.mark.skip(
        reason="No real_las fixtures imported. Run `python run.py --import-real-outputs <path>` first."
    )


@pytest.mark.fixture
@pytest.mark.offline
@pytest.mark.parametrize("fixture_dir", FIXTURES, ids=FIXTURE_IDS or ["none"])
def test_standard_profile_contract(fixture_dir):
    result = validate_standard_output(fixture_dir, "standard")
    assert result.get("passed"), f"standard contract failed for {fixture_dir}: {result}"


@pytest.mark.fixture
@pytest.mark.offline
@pytest.mark.parametrize("fixture_dir", FIXTURES, ids=FIXTURE_IDS or ["none"])
def test_run_meta_authenticity_fields(fixture_dir):
    meta = read_run_meta(fixture_dir)
    for k in ("execution_backend", "output_source", "is_synthetic", "count_as_real_evaluation"):
        assert k in meta, f"run_meta.json missing {k} in {fixture_dir}"


@pytest.mark.fixture
@pytest.mark.offline
@pytest.mark.parametrize("fixture_dir", FIXTURES, ids=FIXTURE_IDS or ["none"])
def test_quality_checks_statistics(fixture_dir):
    qc = read_quality_checks(fixture_dir)
    assert "table_statistics" in qc, f"quality_checks.json missing table_statistics in {fixture_dir}"
    assert "metric_statistics" in qc, f"quality_checks.json missing metric_statistics in {fixture_dir}"
    assert "data_authenticity" in qc


@pytest.mark.smoke
@pytest.mark.fixture
@pytest.mark.offline
def test_byd_fixture_has_financial_tables_if_present():
    byd = next((f for f in FIXTURES if "byd" in f.name.lower()), None)
    if byd is None:
        pytest.skip("BYD fixture not imported")
    qc = read_quality_checks(byd)
    assert (qc.get("table_statistics") or {}).get("financial_table_count", 0) >= 1


@pytest.mark.fixture
@pytest.mark.offline
def test_huadian_fixture_is_non_standard_report():
    huadian = next((f for f in FIXTURES if "华电" in f.name or "huadian" in f.name.lower()), None)
    if huadian is None:
        pytest.skip("Huadian fixture not imported")
    qc = read_quality_checks(huadian)
    stats = qc.get("table_statistics") or {}
    # 华电 PDF is non-standard: zero financial tables is the expected, documented outcome — not a failure.
    assert stats.get("raw_table_count", 0) >= 1
    assert stats.get("financial_table_count", 0) == 0
