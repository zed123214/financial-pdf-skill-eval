"""Dashboard 数据聚合层（纯读盘）。

本模块为 Streamlit 展示 Dashboard 生成一个静态数据包
``reports/dashboard/dashboard_bundle.json``。

== 最高优先级约束：只读已落盘产物 ==

``build_dashboard_bundle()`` 及其调用链必须**纯读盘**，不得触发任何评估、
推理、pipeline、Skill 调用或 patch gate。

允许的读取方式：
    - ``Path.read_text``
    - ``json.loads``
    - ``yaml.safe_load``
    - ``output_contract.read_run_meta``
    - ``output_contract.read_quality_checks``
    - 本模块内的 ``safe_read_json`` / ``safe_read_text``

禁止调用：
    - ``report_collector.summarize_case()``
    - ``gt_evaluator.evaluate()``
    - ``pipeline.run_pipeline()``
    - ``skill_invoker.invoke()``
    - ``llm_judge.run_for_case()``
    - ``optimizer.gate.run_gate()``

``gt_eval_result`` 仅当 ``evaluation/gt_eval_result.json`` 已存在时读取；
不存在则为 ``{}``，绝不触发任何评估。

每个 case 的 ``summary`` 字段在本模块内从已读 JSON 组装，字段对齐
``report_collector.summarize_case`` 的输出格式即可（仅作格式参考，不调用）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from framework.context import FRAMEWORK_ROOT
from framework import output_contract, run_trace


# 默认偏好（仅作为 UI 默认选中项，分数等数据仍从 JSON 动态读取）。
DEFAULT_CASE_ID = "byd_real_las_fixture"

CASES_DIR = FRAMEWORK_ROOT / "testcases" / "pdf_cases"
TRACES_DIR = FRAMEWORK_ROOT / "reports" / "traces"
PROPOSED_PATCHES_DIR = FRAMEWORK_ROOT / "reports" / "optimization" / "proposed_patches"
RUBRIC_PATH = FRAMEWORK_ROOT / "judge" / "assessment_skill.md"
JUDGE_CONFIG_PATH = FRAMEWORK_ROOT / "configs" / "judge.yaml"
DEFAULT_BUNDLE_PATH = FRAMEWORK_ROOT / "reports" / "dashboard" / "dashboard_bundle.json"

# standard profile 必需产物（用于 output_contract 通过性的只读判断）。
STANDARD_REQUIRED = [
    "raw/parsed.md",
    "normalized/normalized_tables.json",
    "normalized/financial_summary.json",
    "evaluation/quality_checks.json",
    "meta/run_meta.json",
]


def _resolve(p: str | Path) -> Path:
    """相对路径一律相对 FRAMEWORK_ROOT 解析（Windows 路径兼容）。"""
    path = Path(p)
    if path.is_absolute():
        return path
    return (FRAMEWORK_ROOT / path).resolve()


def safe_read_json(path: str | Path, default: Any = None) -> Any:
    """安全读取 JSON：文件不存在或解析失败时返回 default。"""
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def safe_read_text(path: str | Path, max_chars: int | None = None) -> str | None:
    """安全读取文本，可选截断；文件不存在或读取失败时返回 None。"""
    p = Path(path)
    if not p.exists():
        return None
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars] + f"\n\n... [已截断，原文共 {len(text)} 字符] ..."
    return text


def _safe_read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def discover_case_files() -> list[Path]:
    """扫描 testcases/pdf_cases/*.yaml，返回单 case YAML 文件列表。

    多 case YAML（如 abnormal_cases.yaml，顶层含 ``cases`` 键）跳过。
    """
    if not CASES_DIR.exists():
        return []
    out: list[Path] = []
    for f in sorted(CASES_DIR.glob("*.yaml")):
        data = _safe_read_yaml(f)
        if isinstance(data, dict) and "cases" in data:
            continue  # 多 case 文件，跳过
        if isinstance(data, dict) and data.get("case_id"):
            out.append(f)
    return out


def _build_summary(case: dict, output_dir: Path, run_meta: dict, quality_checks: dict,
                   score_result: dict, judge_result: dict, gt_eval_result: dict) -> dict:
    """从已读 JSON 组装 summary，字段对齐 report_collector.summarize_case 输出。

    注意：此处**不**调用 summarize_case / validate_standard_output /
    gt_evaluator.evaluate，全部从已落盘数据派生，保证纯读盘。
    """
    table_stats = quality_checks.get("table_statistics") or {}
    metric_stats = quality_checks.get("metric_statistics") or {}
    auth = quality_checks.get("data_authenticity") or {}

    # output_contract 通过性：只做本地文件存在性检查（只读），不跑 Skill validator。
    contract_passed = all((output_dir / rel).exists() for rel in STANDARD_REQUIRED)

    raw_real_eval = auth.get("count_as_real_evaluation", run_meta.get("count_as_real_evaluation"))
    execution_backend = auth.get("execution_backend") or run_meta.get("execution_backend")
    count_as_real_execution = bool(raw_real_eval) and execution_backend in {"real_las", "real_openclaw"}

    has_gt = bool(gt_eval_result)
    no_ground_truth = not has_gt
    case_no_accuracy = case.get("count_as_real_evaluation") is False
    count_as_accuracy_evaluation = has_gt and not case_no_accuracy

    return {
        "case_id": case.get("case_id"),
        "case_name": case.get("name", case.get("case_id")),
        "backend": case.get("backend"),
        "output_profile": case.get("output_profile", "standard"),
        "output_dir": str(output_dir),
        "run_status": run_meta.get("status", "unknown"),
        "output_contract_passed": contract_passed,
        "execution_backend": execution_backend,
        "output_source": run_meta.get("output_source"),
        "is_synthetic": auth.get("is_synthetic", run_meta.get("is_synthetic")),
        "count_as_real_evaluation": raw_real_eval,
        "count_as_real_execution": count_as_real_execution,
        "count_as_accuracy_evaluation": count_as_accuracy_evaluation,
        "page_count": run_meta.get("page_count", run_meta.get("input_page_count")),
        "estimated_price": run_meta.get("estimated_price"),
        "raw_table_count": table_stats.get("raw_table_count"),
        "financial_table_count": table_stats.get("financial_table_count"),
        "layout_table_count": table_stats.get("layout_table_count"),
        "signature_table_count": table_stats.get("signature_table_count"),
        "unknown_table_count": table_stats.get("unknown_table_count"),
        "metric_record_count": metric_stats.get("metric_record_count"),
        "unique_item_count": metric_stats.get("unique_item_count"),
        "unique_statement_count": metric_stats.get("unique_statement_count"),
        "exact_match_accuracy": gt_eval_result.get("exact_match_accuracy"),
        "numeric_accuracy": gt_eval_result.get("numeric_accuracy"),
        "failed_items_count": len(gt_eval_result.get("failed_items") or []) if has_gt else None,
        "no_ground_truth": no_ground_truth,
        "eligible_count": gt_eval_result.get("eligible_count"),
        "weighted_score": score_result.get("weighted_score"),
        "level": score_result.get("level"),
    }


def _patch_target_tokens(patch: dict) -> set[str]:
    """从 patch JSON 收集可用于匹配 suggested_targets 的 token 集合。"""
    tokens: set[str] = set()
    target_file = patch.get("target_file")
    if target_file:
        tokens.add(Path(str(target_file)).stem)
    change = patch.get("change") or {}
    if isinstance(change, dict) and change.get("rule_id"):
        tokens.add(str(change["rule_id"]))
    if patch.get("patch_id"):
        tokens.add(str(patch["patch_id"]))
    # 一些 patch 用 suggested_target / target 字段
    for key in ("target", "suggested_target"):
        val = patch.get(key)
        if isinstance(val, str):
            tokens.add(val)
        elif isinstance(val, list):
            tokens.update(str(x) for x in val)
    return {t for t in tokens if t}


def load_all_patches() -> list[dict]:
    """读取 reports/optimization/proposed_patches/*.json。"""
    if not PROPOSED_PATCHES_DIR.exists():
        return []
    patches: list[dict] = []
    for f in sorted(PROPOSED_PATCHES_DIR.glob("*.json")):
        data = safe_read_json(f, default=None)
        if isinstance(data, dict):
            data.setdefault("_file", f.name)
            patches.append(data)
    return patches


def _associate_patches(case_id: str, suggested_targets: list[str],
                       all_patches: list[dict]) -> tuple[list[dict], set[int]]:
    """关联与某 case 相关的 patches，返回 (相关 patch 列表, 已归属的 patch 索引集合)。

    关联规则：
      1. patch.case_id == 当前 case_id；
      2. patch 的 target / target_file / rule_id 与 failure_trace.suggested_targets 有交集。
    否则不归属（留作全局 patch）。
    """
    related: list[dict] = []
    claimed: set[int] = set()
    targets = {str(t) for t in (suggested_targets or [])}
    for idx, patch in enumerate(all_patches):
        matched = False
        if patch.get("case_id") and str(patch["case_id"]) == str(case_id):
            matched = True
        if not matched and targets:
            if _patch_target_tokens(patch) & targets:
                matched = True
        if matched:
            related.append(patch)
            claimed.add(idx)
    return related, claimed


def _load_one_case(yaml_path: Path, all_patches: list[dict]) -> tuple[dict, set[int]]:
    """加载单个 case 的完整 Dashboard 数据；返回 (case_dict, 已归属 patch 索引)。"""
    data = _safe_read_yaml(yaml_path) or {}
    case_id = data.get("case_id")
    missing_files: list[str] = []

    raw_output_dir = data.get("output_dir")
    output_dir = _resolve(raw_output_dir) if raw_output_dir else None

    run_meta: dict = {}
    quality_checks: dict = {}
    score_result: dict = {}
    judge_result: dict = {}
    gt_eval_result: dict = {}
    summary: dict = {}
    artifacts = {"parsed_md_path": None, "normalized_tables_path": None}
    run_trace_bundle = run_trace.load_trace_bundle(output_dir)

    if output_dir is not None:
        if not output_dir.exists():
            missing_files.append(str(output_dir))
        else:
            run_meta = output_contract.read_run_meta(output_dir) or {}
            quality_checks = output_contract.read_quality_checks(output_dir) or {}
            score_result = safe_read_json(output_dir / "evaluation" / "score_result.json", {}) or {}
            judge_result = safe_read_json(output_dir / "evaluation" / "judge_result.json", {}) or {}

            # gt_eval_result：仅当文件已存在时读取，否则保持 {}，绝不触发评估。
            gt_path = output_dir / "evaluation" / "gt_eval_result.json"
            if gt_path.exists():
                gt_eval_result = safe_read_json(gt_path, {}) or {}

            # 逐个产物文件做存在性检查并记录缺失。
            for rel in STANDARD_REQUIRED:
                if not (output_dir / rel).exists():
                    missing_files.append(rel)

            parsed_md = output_dir / "raw" / "parsed.md"
            normalized_tables = output_dir / "normalized" / "normalized_tables.json"
            artifacts["parsed_md_path"] = str(parsed_md) if parsed_md.exists() else None
            artifacts["normalized_tables_path"] = str(normalized_tables) if normalized_tables.exists() else None

            summary = _build_summary(
                data, output_dir, run_meta, quality_checks,
                score_result, judge_result, gt_eval_result,
            )

    # failure_trace
    failure_trace: dict = {}
    if case_id:
        ft_path = TRACES_DIR / f"{case_id}_failure_trace.json"
        if ft_path.exists():
            failure_trace = safe_read_json(ft_path, {}) or {}
        else:
            missing_files.append(f"reports/traces/{case_id}_failure_trace.json")

    suggested_targets = failure_trace.get("suggested_targets") or []
    related_patches, claimed = _associate_patches(case_id, suggested_targets, all_patches)

    case_entry = {
        "case_id": case_id,
        "name": data.get("name", case_id),
        "yaml_path": str(yaml_path),
        "output_dir": str(output_dir) if output_dir is not None else None,
        "summary": summary,
        "run_meta": run_meta,
        "quality_checks": quality_checks,
        "score_result": score_result,
        "judge_result": judge_result,
        "gt_eval_result": gt_eval_result,
        "failure_trace": failure_trace,
        "run_trace": run_trace_bundle,
        "patches": related_patches,
        "artifacts": artifacts,
        "missing_files": missing_files,
    }
    return case_entry, claimed


def load_dashboard_cases() -> tuple[list[dict], list[dict]]:
    """加载全部单 case 数据，返回 (cases, global_patches)。

    未归属到任何 case 的 patch 作为全局 patch 返回。
    """
    all_patches = load_all_patches()
    cases: list[dict] = []
    all_claimed: set[int] = set()
    for yaml_path in discover_case_files():
        entry, claimed = _load_one_case(yaml_path, all_patches)
        cases.append(entry)
        all_claimed |= claimed
    global_patches = [p for i, p in enumerate(all_patches) if i not in all_claimed]
    return cases, global_patches


def build_dashboard_bundle(output_path: str | Path | None = None) -> dict:
    """生成 Dashboard 数据包并写入磁盘，返回 bundle dict。

    纯读盘：仅扫描并读取已落盘的 JSON / Markdown / YAML，不触发任何评估或推理。
    """
    cases, global_patches = load_dashboard_cases()
    judge_config = _safe_read_yaml(JUDGE_CONFIG_PATH) or {}

    bundle = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "framework_root": str(FRAMEWORK_ROOT),
        "default_case_id": DEFAULT_CASE_ID,
        "rubric_path": "judge/assessment_skill.md",
        "rubric_exists": RUBRIC_PATH.exists(),
        "judge_config_path": "configs/judge.yaml",
        "judge_config": judge_config,
        "global_patches": global_patches,
        "cases": cases,
    }

    out_path = _resolve(output_path) if output_path else DEFAULT_BUNDLE_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    bundle["_bundle_path"] = str(out_path)
    return bundle


if __name__ == "__main__":
    b = build_dashboard_bundle()
    print(f"wrote {b['_bundle_path']} with {len(b['cases'])} cases")
