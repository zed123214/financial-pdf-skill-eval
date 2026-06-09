"""Data authenticity assertions on real_las output fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.context import FRAMEWORK_ROOT
from framework.output_contract import read_quality_checks, read_run_meta


REAL_LAS_DIR = FRAMEWORK_ROOT / "data" / "real_las_outputs"


def _fixtures():
    if not REAL_LAS_DIR.exists():
        return []
    return [p for p in sorted(REAL_LAS_DIR.iterdir()) if p.is_dir() and (p / "meta" / "run_meta.json").exists()]


FIXTURES = _fixtures()

if not FIXTURES:
    pytestmark = pytest.mark.skip(reason="No real_las fixtures imported.")


@pytest.mark.fixture
@pytest.mark.offline
@pytest.mark.parametrize("fixture_dir", FIXTURES, ids=[f.name for f in FIXTURES] or ["none"])
def test_run_meta_required_authenticity_fields(fixture_dir):
    meta = read_run_meta(fixture_dir)
    for k in ("execution_backend", "output_source", "is_synthetic", "count_as_real_evaluation"):
        assert k in meta, f"{fixture_dir}: run_meta missing {k}"


@pytest.mark.fixture
@pytest.mark.offline
@pytest.mark.parametrize("fixture_dir", FIXTURES, ids=[f.name for f in FIXTURES] or ["none"])
def test_synthetic_must_not_count_as_real(fixture_dir):
    meta = read_run_meta(fixture_dir)
    qc = read_quality_checks(fixture_dir)
    auth = qc.get("data_authenticity") or {}
    is_synth = auth.get("is_synthetic", meta.get("is_synthetic"))
    count_real = auth.get("count_as_real_evaluation", meta.get("count_as_real_evaluation"))
    if is_synth:
        assert count_real is False, f"{fixture_dir}: is_synthetic=true but count_as_real_evaluation={count_real}"


@pytest.mark.fixture
@pytest.mark.offline
@pytest.mark.parametrize("fixture_dir", FIXTURES, ids=[f.name for f in FIXTURES] or ["none"])
def test_real_las_is_not_real_openclaw(fixture_dir):
    meta = read_run_meta(fixture_dir)
    backend = meta.get("execution_backend")
    if backend == "real_las":
        # real_las must not be relabeled as real_openclaw in output_source
        assert meta.get("output_source") != "real_openclaw", fixture_dir


@pytest.mark.fixture
@pytest.mark.offline
@pytest.mark.parametrize("fixture_dir", FIXTURES, ids=[f.name for f in FIXTURES] or ["none"])
def test_count_as_real_without_gt_is_real_execution_not_accuracy(fixture_dir):
    """count_as_real_evaluation=true only certifies real execution.
    Accuracy still requires a Ground Truth — gt_eval_result.json must exist for accuracy claims."""
    meta = read_run_meta(fixture_dir)
    if meta.get("count_as_real_evaluation"):
        # ok — but there is NO assertion that accuracy is measured here.
        # If a gt_eval_result.json is present, it must be schema-valid; otherwise the case is
        # counted only for "real execution sample", not for accuracy.
        gt_eval = fixture_dir / "evaluation" / "gt_eval_result.json"
        if gt_eval.exists():
            import json
            data = json.loads(gt_eval.read_text(encoding="utf-8"))
            assert "numeric_accuracy" in data or "exact_match_accuracy" in data
