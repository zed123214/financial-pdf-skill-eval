from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def case_dirs(outputs_dir: Path) -> list[Path]:
    if not outputs_dir.exists():
        return []
    return sorted(
        path
        for path in outputs_dir.iterdir()
        if path.is_dir() and ((path / "meta" / "run_meta.json").is_file() or (path / "run_meta.json").is_file())
    )


def case_meta(case_dir: Path) -> dict[str, Any]:
    return read_json(case_dir / "meta" / "run_meta.json") or read_json(case_dir / "run_meta.json")


def case_quality(case_dir: Path) -> dict[str, Any]:
    return read_json(case_dir / "evaluation" / "quality_checks.json")


def case_gt(case_dir: Path) -> dict[str, Any]:
    return read_json(case_dir / "evaluation" / "gt_eval_result.json")


def case_row(case_dir: Path) -> str:
    meta = case_meta(case_dir)
    quality = case_quality(case_dir)
    table_stats = quality.get("table_statistics", {})
    metric_stats = quality.get("metric_statistics", {})
    return (
        f"| {case_dir.name} | {meta.get('input_file', '')} | {meta.get('page_count', '')} | "
        f"{meta.get('execution_backend', 'unknown')} | {meta.get('output_source', 'unknown')} | "
        f"{meta.get('is_synthetic', False)} | {meta.get('count_as_real_evaluation', False)} | "
        f"{table_stats.get('raw_table_count', meta.get('raw_table_count', 0))} | "
        f"{table_stats.get('financial_table_count', meta.get('financial_table_count', 0))} | "
        f"{metric_stats.get('metric_record_count', meta.get('metric_record_count', 0))} |"
    )


def generate(outputs_dir: Path, report: Path) -> Path:
    cases = case_dirs(outputs_dir)
    has_real_openclaw = any(case_meta(case).get("execution_backend") == "real_openclaw" for case in cases)
    gt_cases = [(case.name, case_gt(case)) for case in cases if case_gt(case)]

    lines = [
        "# 金融财报 PDF 解析 Skill 项目报告",
        "",
        "## 1. 课题背景",
        "",
        "训练营课题要求基于 OpenClaw 实现数据处理 Skill。PDF 方向关注金融财报、复杂表格、密集数值、扫描件和多页文档，并需要完整链路与系统性评测。",
        "",
        "## 2. Skill 设计",
        "",
        "- base skill: byted-las-pdf-parse-doubao",
        "- current skill: financial-pdf-parse-doubao-eval",
        "- 当前 Skill 不是重写 OCR，而是对 LAS Doubao PDF Parse 做金融财报领域增强封装。",
        "",
        "## 3. OpenClaw 调用链路",
        "",
        "- Skill 通过 `skills/financial-pdf-parse-doubao-eval/SKILL.md` 暴露给 OpenClaw。",
        "- Skill 目录包含 `_meta.json`、references、scripts、evals 和 examples。",
        "- OpenClaw 证据路径：`outputs/openclaw_invocation_log.md`。",
        "- real_las 表示 Skill 内部直接调用 LAS / lasutil，不等同于 real_openclaw 后端调度。",
        "- real_openclaw backend " + ("已检测到运行元数据。" if has_real_openclaw else "尚未完成或尚未验证。"),
        "",
        "## 4. LAS 调用链路",
        "",
        "- `real_las` backend 使用 `lasutil file-upload`、`lasutil submit las_pdf_parse_doubao`、`lasutil poll`。",
        "- detail 模式适合扫描件、复杂表格和正式财报评测。",
        "- task_id、页数、费用估算写入 `run_meta.json`。",
        "",
        "## 5. 数据集",
        "",
        "| case_id | input file | page_count | execution_backend | output_source | is_synthetic | count_as_real_evaluation | raw_table_count | financial_table_count | metric_record_count |",
        "|---|---|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    lines.extend(case_row(case) for case in cases)
    lines.extend(
        [
            "",
            "## 6. 评测指标",
            "",
            "- 输出完整性检查：文件存在性、JSON 合法性、Markdown 非空、schema 完整性、数据来源标记。",
            "- 表格统计：raw_table_count、financial_table_count、layout_table_count、signature_table_count、unknown_table_count。",
            "- 财务指标统计：metric_record_count、unique_item_count、unique_statement_count。",
            "- Ground Truth exact_match_accuracy：人工 expected 与 actual 原始字符串一致率。",
            "- Ground Truth numeric_accuracy：金额标准化后 0.01 以内误差匹配率。",
            "- financial balance check、negative number check、decimal check、period alignment check。",
            "- 输出完整性不等于准确率。",
            "- 准确率以 gt_eval_result.json 为准。",
            "",
            "## 7. 运行结果",
            "",
        ]
    )
    for case in cases:
        meta = case_meta(case)
        quality = case_quality(case)
        gt = case_gt(case)
        lines.extend(
            [
                f"### {case.name}",
                f"- execution_backend: {meta.get('execution_backend', 'unknown')}",
                f"- output_source: {meta.get('output_source', 'unknown')}",
                f"- output_profile: {meta.get('output_profile', 'unknown')}",
                f"- status: {meta.get('status', 'unknown')}",
                f"- raw_table_count: {quality.get('table_statistics', {}).get('raw_table_count', meta.get('raw_table_count', 0))}",
                f"- financial_table_count: {quality.get('table_statistics', {}).get('financial_table_count', meta.get('financial_table_count', 0))}",
                f"- metric_record_count: {quality.get('metric_statistics', {}).get('metric_record_count', meta.get('metric_record_count', 0))}",
                f"- gt_exact_match_accuracy: {gt.get('exact_match_accuracy', 'N/A')}",
                f"- gt_numeric_accuracy: {gt.get('numeric_accuracy', 'N/A')}",
                "",
            ]
        )
    lines.extend(
        [
            "## 8. 成功案例",
            "",
            "1. real_las case 可完成 LAS 解析并生成标准输出。",
            "2. 财报 PDF 可通过后处理抽取资产负债表、利润表、现金流量表和关键财务指标。",
            "3. Skill 输出 raw / normalized / evaluation / meta 分层结果，便于外层自动化测评框架消费。",
            "",
            "## 9. 失败 / 风险案例",
            "",
            "1. 表格数量可能包含签名表、布局表，不能直接等同财务表数量。",
            "2. 指标数量代表抽取记录数，不等于人工准确率。",
            "3. real_las 不等于 real_openclaw。",
            "4. 没有人工 Ground Truth 的 case 不能计入真实准确率。",
            "5. 单位换算存在风险，例如元、万元、亿元。",
            "",
            "## 10. 异常场景",
            "",
            "- 文件不存在：待自动化测试框架补充或通过 error_result.json 汇总。",
            "- 非 PDF 文件：待自动化测试框架补充或通过 error_result.json 汇总。",
            "- LAS_API_KEY 缺失：待自动化测试框架补充或通过 error_result.json 汇总。",
            "- result.json 缺少 data.markdown：待自动化测试框架补充。",
            "- pages_detail 缺失：standard 默认不要求，debug / --keep-pages-detail 可检查。",
            "- task timeout：待自动化测试框架补充。",
            "",
            "## 11. 当前限制",
            "",
            "- real_openclaw backend 尚未完成或尚未验证。" if not has_real_openclaw else "- real_openclaw backend 已有元数据，但仍建议补充调用日志。",
            "- 当前样本数量有限。",
            "- Ground Truth 人工核验仍需扩展。",
            "- 当前财务表分类是启发式规则。",
            "- 输出完整性检查不能替代准确率评测。",
            "",
            "## 12. 后续优化",
            "",
            "- 扩展 20–30 个样本。",
            "- 完善人工标注 Ground Truth。",
            "- 接入 Pytest/YAML 自动化评测框架。",
            "- 增加 Allure 附件。",
            "- 增加 CI。",
            "- 优化跨页表格、阅读顺序、单位识别。",
        ]
    )
    if gt_cases:
        lines.extend(["", "## Ground Truth 汇总", ""])
        for case_id, gt in gt_cases:
            lines.append(f"- {case_id}: exact={gt.get('exact_match_accuracy')}, numeric={gt.get('numeric_accuracy')}")

    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate final project report for financial PDF Skill.")
    parser.add_argument("--outputs-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    path = generate(args.outputs_dir, args.report)
    print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
