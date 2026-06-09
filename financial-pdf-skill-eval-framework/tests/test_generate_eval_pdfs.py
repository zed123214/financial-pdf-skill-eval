"""Contract tests for the synthetic financial PDF dataset generator."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import yaml

from framework.context import FRAMEWORK_ROOT


GENERATOR_PATH = FRAMEWORK_ROOT / "tools" / "generate_eval_pdfs.py"
EXPECTED_CASE_IDS = [
    "input_007_income_statement",
    "input_008_cashflow_supplement",
    "input_009_balance_sheet_assets",
    "input_010_bilingual_income_statement",
    "input_011_cross_page_income_statement",
    "input_012_no_border_financial_table",
    "input_013_multi_header_performance_table",
    "input_014_main_table_with_notes",
    "input_015_low_dpi_scan_sim",
    "input_016_stamp_watermark_table",
    "input_017_header_footer_noise",
    "input_018_meeting_minutes_no_table",
]


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_eval_pdfs", GENERATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_case_catalogue_is_complete_and_single_source():
    generator = load_generator()

    assert [case["case_id"] for case in generator.CASES] == EXPECTED_CASE_IDS
    assert len(generator.CASES) == 12
    for case in generator.CASES:
        for key in (
            "case_id",
            "filename",
            "band",
            "pages",
            "language",
            "tags",
            "image_only",
            "company_name",
            "tables",
            "metrics",
            "yaml_extra",
            "diff_note",
        ):
            assert key in case, f"{case.get('case_id')} missing {key}"
        assert case["filename"] == f"{case['case_id']}.pdf"
        if case["case_id"] == "input_018_meeting_minutes_no_table":
            assert case["metrics"] == []
        else:
            assert 5 <= len(case["metrics"]) <= 12
    assert generator.by_id("input_015_low_dpi_scan_sim")["image_only"] is True
    assert generator.by_id("input_016_stamp_watermark_table")["image_only"] is True


def test_gt_export_uses_todo_source_and_promotes_only_when_requested(tmp_path, monkeypatch):
    generator = load_generator()
    monkeypatch.setattr(generator, "ROOT", tmp_path)

    case = generator.by_id("input_007_income_statement")
    gt_path = generator.export_gt(case)
    data = json.loads(gt_path.read_text(encoding="utf-8"))
    assert data["source"] == "todo_manual_verify"
    assert data["metrics"][0]["expected"] == case["metrics"][0]["expected"]
    assert data["metrics"][0]["unit"] == case["metrics"][0]["unit"]
    assert "Human verification date:" not in data["note"]

    promoted = json.loads(generator.export_gt(case, promote_verified=True).read_text(encoding="utf-8"))
    assert promoted["source"] == "manual_verified"
    assert "Human verification date:" in promoted["note"]


def test_yaml_exports_framework_compatible_validations(tmp_path, monkeypatch):
    generator = load_generator()
    monkeypatch.setattr(generator, "ROOT", tmp_path)

    normal = yaml.safe_load(generator.export_yaml(generator.by_id("input_007_income_statement")).read_text(encoding="utf-8"))
    assert normal["backend"] == "fixture"
    assert normal["output_dir"] == "data/real_las_outputs/input_007_income_statement"
    assert not any(v["type"] == "data_authenticity" for v in normal["validations"])
    assert {"type": "metric_stat_ge", "field": "metric_record_count", "expected": 5} in normal["validations"]
    assert {"type": "table_stat_ge", "field": "financial_table_count", "expected": 1} in normal["validations"]

    image = yaml.safe_load(generator.export_yaml(generator.by_id("input_015_low_dpi_scan_sim")).read_text(encoding="utf-8"))
    gt_checks = [v for v in image["validations"] if v["type"] == "gt_numeric_accuracy_ge"]
    assert gt_checks == [{"type": "gt_numeric_accuracy_ge", "threshold": 0.5, "skip_if_no_ground_truth": True}]
    assert "image-only PDF" in image["description"]

    no_table = yaml.safe_load(generator.export_yaml(generator.by_id("input_018_meeting_minutes_no_table")).read_text(encoding="utf-8"))
    assert {"type": "table_stat_eq", "field": "financial_table_count", "expected": 0} in no_table["validations"]
    assert {"type": "metric_stat_eq", "field": "metric_record_count", "expected": 0} in no_table["validations"]


def test_manifest_contains_all_cases_and_integration_steps(tmp_path, monkeypatch):
    generator = load_generator()
    monkeypatch.setattr(generator, "ROOT", tmp_path)

    manifest_path = generator.export_manifest()
    text = manifest_path.read_text(encoding="utf-8")
    for case_id in EXPECTED_CASE_IDS:
        assert f"| {case_id}.pdf | {case_id} |" in text
    assert "python tools/generate_eval_pdfs.py" in text
    assert "python run.py --build-dashboard-bundle" in text
    assert "| input_018_meeting_minutes_no_table.pdf | input_018_meeting_minutes_no_table | boundary | 1 | false | 0 | todo_manual_verify |" in text
