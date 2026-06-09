"""Dashboard 数据聚合层离线测试。

约束：纯读盘，不访问网络，不调用真实 LAS / OpenClaw。
"""
from __future__ import annotations

import json

import pytest

from framework import dashboard_bundle, run_trace
from framework.context import FRAMEWORK_ROOT

pytestmark = pytest.mark.offline


@pytest.mark.offline
def test_build_returns_dict():
    bundle = dashboard_bundle.build_dashboard_bundle()
    assert isinstance(bundle, dict)


@pytest.mark.offline
def test_top_level_keys():
    bundle = dashboard_bundle.build_dashboard_bundle()
    assert "generated_at" in bundle
    assert "cases" in bundle
    assert isinstance(bundle["cases"], list)


@pytest.mark.offline
def test_bundle_written_to_disk():
    bundle = dashboard_bundle.build_dashboard_bundle()
    out_path = FRAMEWORK_ROOT / "reports" / "dashboard" / "dashboard_bundle.json"
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert "cases" in data
    assert isinstance(data["cases"], list)


@pytest.mark.offline
def test_byd_case_structure_if_present():
    bundle = dashboard_bundle.build_dashboard_bundle()
    byd = next(
        (c for c in bundle["cases"] if c.get("case_id") == "byd_real_las_fixture"),
        None,
    )
    if byd is None:
        pytest.skip("byd_real_las_fixture 不存在，跳过结构检查")
    for key in ("case_id", "output_dir", "summary", "missing_files",
                "score_result", "failure_trace"):
        assert key in byd, f"byd case 缺少字段 {key}"
    assert isinstance(byd["missing_files"], list)
    assert isinstance(byd["summary"], dict)


@pytest.mark.offline
def test_safe_read_json_missing_returns_default(tmp_path):
    missing = tmp_path / "nope.json"
    assert dashboard_bundle.safe_read_json(missing, default={}) == {}


@pytest.mark.offline
def test_safe_read_text_truncates(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * 100, encoding="utf-8")
    out = dashboard_bundle.safe_read_text(f, max_chars=10)
    assert out is not None
    assert out.startswith("x" * 10)
    assert "已截断" in out


@pytest.mark.offline
def test_discover_skips_multi_case_yaml():
    """多 case YAML（abnormal_cases.yaml）不应出现在单 case 列表中。"""
    files = dashboard_bundle.discover_case_files()
    names = [f.name for f in files]
    assert "abnormal_cases.yaml" not in names


@pytest.mark.offline
def test_gt_eval_result_only_when_file_exists():
    """gt_eval_result 必须来自已落盘文件；缺失时为 {}，绝不触发评估。"""
    cases, _ = dashboard_bundle.load_dashboard_cases()
    for c in cases:
        gt = c.get("gt_eval_result")
        assert isinstance(gt, dict)
        output_dir = c.get("output_dir")
        if output_dir:
            from pathlib import Path

            gt_path = Path(output_dir) / "evaluation" / "gt_eval_result.json"
            if not gt_path.exists():
                assert gt == {}, f"{c.get('case_id')} 无 gt 文件却有 gt_eval_result"


@pytest.mark.offline
def test_case_entry_includes_run_trace_from_output_dir(tmp_path):
    output_dir = tmp_path / "case_output"
    output_dir.mkdir()
    writer = run_trace.RunTraceWriter(
        output_dir / "trace" / "events.jsonl",
        case_id="trace_case",
        backend="fixture",
    )
    writer.emit("run_started", status="running", data={"case_name": "Trace Case"})

    yaml_path = tmp_path / "trace_case.yaml"
    yaml_path.write_text(
        "\n".join([
            "case_id: trace_case",
            "name: Trace Case",
            "backend: fixture",
            f"output_dir: {output_dir}",
        ]),
        encoding="utf-8",
    )

    case_entry, claimed = dashboard_bundle._load_one_case(yaml_path, [])

    assert claimed == set()
    assert "run_trace" in case_entry
    assert case_entry["run_trace"]["exists"] is True
    assert case_entry["run_trace"]["path"].replace("\\", "/").endswith("trace/events.jsonl")
    assert case_entry["run_trace"]["summary"]["event_count"] == 1
    assert case_entry["run_trace"]["events"][0]["kind"] == "run_started"
