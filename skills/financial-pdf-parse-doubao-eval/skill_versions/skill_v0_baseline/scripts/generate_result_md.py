from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def first_existing(output_dir: Path, paths: list[str]) -> Path | None:
    for relative in paths:
        path = output_dir / relative
        if path.exists():
            return path
    return None


def preview(output_dir: Path, limit: int = 500) -> str:
    path = first_existing(output_dir, ["raw/parsed.md", "parsed.md"])
    if not path:
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()[:limit]


def output_files(output_dir: Path) -> list[str]:
    candidates = [
        "parsed.md",
        "financial_summary.json",
        "evaluation_report.md",
        "run_meta.json",
        "raw/parsed.md",
        "raw/result.json",
        "raw/pages_detail.json",
        "normalized/cleaned.md",
        "normalized/normalized_tables.json",
        "normalized/financial_summary.json",
        "evaluation/quality_checks.json",
        "evaluation/gt_eval_result.json",
        "evaluation/evaluation_report.md",
        "meta/run_meta.json",
        "meta/error_result.json",
    ]
    return [relative for relative in candidates if (output_dir / relative).exists()]


def build_report(output_dir: Path) -> str:
    meta = read_json(first_existing(output_dir, ["meta/run_meta.json", "run_meta.json"]) or output_dir / "missing", {})
    quality = read_json(output_dir / "evaluation" / "quality_checks.json", {})
    gt_result = read_json(output_dir / "evaluation" / "gt_eval_result.json", {})
    table_stats = quality.get("table_statistics", {}) or {
        "raw_table_count": meta.get("raw_table_count", 0),
        "financial_table_count": meta.get("financial_table_count", 0),
        "layout_table_count": meta.get("layout_table_count", 0),
        "signature_table_count": meta.get("signature_table_count", 0),
        "unknown_table_count": meta.get("unknown_table_count", 0),
    }
    metric_stats = quality.get("metric_statistics", {}) or {
        "metric_record_count": meta.get("metric_record_count", 0),
        "unique_item_count": meta.get("unique_item_count", 0),
        "unique_statement_count": meta.get("unique_statement_count", 0),
    }
    checks = quality.get("checks", [])
    completeness_checks = [
        check for check in checks
        if check.get("name") in {
            "table_count_check",
            "financial_statement_detection_check",
            "pages_detail_schema_check",
            "parsed_markdown_non_empty_check",
            "result_business_code_check",
        }
    ]
    completeness_passed = sum(1 for check in completeness_checks if check.get("passed"))
    completeness_total = len(completeness_checks)
    completeness_rate = (completeness_passed / completeness_total) if completeness_total else 0.0

    lines = [
        "# 金融财报 PDF 解析结果",
        "",
        "## 任务信息",
        f"- task_id: {meta.get('task_id', 'N/A')}",
        f"- skill_version: {meta.get('skill_version', '0.3.0')}",
        f"- execution_backend: {meta.get('execution_backend', 'unknown')}",
        f"- output_source: {meta.get('output_source', 'unknown')}",
        f"- parse_mode: {meta.get('parse_mode', 'unknown')}",
        f"- page_count: {meta.get('page_count', 'unknown')}",
        f"- estimated_price: {meta.get('estimated_price', 'unknown')}",
        f"- output_profile: {meta.get('output_profile', 'unknown')}",
        f"- status: {meta.get('status', 'unknown')}",
        f"- is_synthetic: {str(meta.get('is_synthetic', False)).lower()}",
        f"- count_as_real_evaluation: {str(meta.get('count_as_real_evaluation', False)).lower()}",
        "",
        "## 输出文件",
    ]
    lines.extend(f"- {relative}" for relative in output_files(output_dir))
    lines.extend(
        [
            "",
            "## 输出完整性检查",
            f"- 输出完整性检查通过率: {completeness_passed}/{completeness_total} ({completeness_rate:.2%})",
            "- 输出完整性检查通过不等于解析准确率 100%。",
            "- 当前检查项主要覆盖文件存在性、JSON 合法性、Markdown 非空、schema 完整性、数据来源标记等。",
            "- 真实解析准确率必须基于人工 Ground Truth 进行 expected vs actual 对比。",
            "- 解析准确率以 evaluation/gt_eval_result.json 为准。",
            "",
            "## 表格与指标统计",
            f"- raw_table_count: {table_stats.get('raw_table_count', 0)}",
            f"- financial_table_count: {table_stats.get('financial_table_count', 0)}",
            f"- layout_table_count: {table_stats.get('layout_table_count', 0)}",
            f"- signature_table_count: {table_stats.get('signature_table_count', 0)}",
            f"- unknown_table_count: {table_stats.get('unknown_table_count', 0)}",
            f"- metric_record_count: {metric_stats.get('metric_record_count', 0)}",
            f"- unique_item_count: {metric_stats.get('unique_item_count', 0)}",
            f"- unique_statement_count: {metric_stats.get('unique_statement_count', 0)}",
            "- 表格数、指标数代表抽取规模，不代表准确率。",
            "",
            "## Ground Truth 评测",
        ]
    )
    if gt_result:
        lines.extend(
            [
                f"- case_id: {gt_result.get('case_id', '')}",
                f"- ground_truth_source: {gt_result.get('ground_truth_source', '')}",
                f"- exact_match_accuracy: {gt_result.get('exact_match_accuracy', 0)}",
                f"- numeric_accuracy: {gt_result.get('numeric_accuracy', 0)}",
            ]
        )
    else:
        lines.append("- 未发现 evaluation/gt_eval_result.json；该 case 只能作为链路验证或结构抽取验证。")

    if meta.get("execution_backend") == "real_las":
        lines.extend(
            [
                "",
                "## 数据真实性说明",
                "- 当前 backend 为 real_las，表示 Skill 内部直接调用 LAS / lasutil，不等同于 real_openclaw 后端调度。",
            ]
        )

    lines.extend(
        [
            "",
            "## 文本预览",
            "",
            "```text",
            preview(output_dir),
            "```",
            "",
            "## 注意事项",
            "- 图片链接可能过期。",
            "- 预估计费仅供执行前确认，最终费用以火山引擎账单为准。",
            "- official_output_mock 是离线评测，不代表本次发生真实 LAS 调用。",
            "- fallback_synthetic_mock 只能用于框架自检，不计入真实评测。",
            "",
        ]
    )
    return "\n".join(lines)


def generate(output_dir: Path) -> Path:
    meta = read_json(first_existing(output_dir, ["meta/run_meta.json", "run_meta.json"]) or output_dir / "missing", {})
    if meta.get("output_profile") == "minimal":
        path = output_dir / "evaluation_report.md"
    else:
        path = output_dir / "evaluation" / "evaluation_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(output_dir), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate financial PDF parse result markdown report.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()
    path = generate(args.output_dir)
    print(path.read_text(encoding="utf-8") if args.stdout else str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
