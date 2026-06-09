"""optimizer.gate —— SkillOpt validation + regression 门禁（合一，对应 README §10）。

run_gate(patch, ...) 流程：
    1. 静态白名单校验 patch（target_scope/target_file）。
    2. 运行时解析 splits（缺文件 / 缺 fixture 写入 missing_cases，不崩溃）。
    3. apply patch -> .skillopt_workspace/skill_candidate/（skill scope）。
    4. 设置 SKILL_DIR_OVERRIDE 让框架用 candidate Skill 跑 case；结束后清除。
    5. 每 case 跑现有 pipeline 产 score_result，与 baseline_v0_summary.json 对比。
    6. 输出 GateResult（accept | reject + reasons），并写 score_diff_v0_v1.json。
    7. reject 时写 optimizer/rejected_patch_buffer.json。

P0 evaluation_mode 默认 fixture_scores_only：fixture backend 不 re-invoke Skill，
只读已有 output_dir 打分；因此 candidate 分数通常与 baseline 相同（no_regression_accepted），
报告不得据此宣称解析能力提升。

报告写入（Step 6 配套，仍在本模块内，保持仅新增 2 个 Python 文件）：
    reports/optimization/skillopt_iterations.md / accepted_patches.md / rejected_patches.md
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from framework.context import FRAMEWORK_ROOT
from framework.logger import get_logger
from optimizer import skill_patch

LOG = get_logger("gate")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SKILLOPT_CONFIG = FRAMEWORK_ROOT / "configs" / "skillopt.yaml"
BASELINE_SUMMARY = FRAMEWORK_ROOT / "reports" / "baseline" / "baseline_v0_summary.json"
OPT_DIR = FRAMEWORK_ROOT / "reports" / "optimization"
SCORE_DIFF_PATH = OPT_DIR / "score_diff_v0_v1.json"
REJECTED_BUFFER = FRAMEWORK_ROOT / "optimizer" / "rejected_patch_buffer.json"
ITERATIONS_MD = OPT_DIR / "skillopt_iterations.md"
ACCEPTED_MD = OPT_DIR / "accepted_patches.md"
REJECTED_MD = OPT_DIR / "rejected_patches.md"

STANDARD_REQUIRED = [
    "raw/parsed.md",
    "normalized/normalized_tables.json",
    "normalized/financial_summary.json",
    "evaluation/quality_checks.json",
    "meta/run_meta.json",
]

PASS_DIMENSION_SCORE = 10  # boolean_pass_score in pdf_financial_score.yaml


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _resolve(p: str | Path) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (FRAMEWORK_ROOT / path).resolve()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_skillopt_config(path: Path | None = None) -> dict[str, Any]:
    p = path or SKILLOPT_CONFIG
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def load_baseline_summary(path: Path | None = None) -> dict[str, Any]:
    p = path or BASELINE_SUMMARY
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _baseline_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for c in summary.get("cases") or []:
        cid = c.get("case_id")
        if cid:
            out[cid] = c
    return out


# ---------------------------------------------------------------------------
# split resolution（运行时，缺失即跳过并记录，不造假 case）
# ---------------------------------------------------------------------------
def resolve_splits(splits_config: dict[str, Any]) -> tuple[dict[str, list[dict]], list[dict]]:
    """返回 (resolved_cases_by_split, missing_cases)。

    resolved_cases_by_split[split] = [case_dict, ...]（已 load_case）。
    missing_cases = [{case_yaml, reason}]，reason ∈ yaml_missing|fixture_missing|output_dir_invalid。
    """
    from framework import case_loader

    resolved: dict[str, list[dict]] = {}
    missing: list[dict] = []
    for split, paths in (splits_config or {}).items():
        resolved[split] = []
        for rel in paths or []:
            yaml_path = _resolve(rel)
            if not yaml_path.exists():
                missing.append({"case_yaml": rel, "reason": "yaml_missing"})
                continue
            try:
                case = case_loader.load_case(yaml_path)
            except Exception as exc:
                LOG.warning("failed to load case %s: %s", rel, exc)
                missing.append({"case_yaml": rel, "reason": "yaml_missing"})
                continue
            out_dir_raw = case.get("output_dir")
            if not out_dir_raw:
                missing.append({"case_yaml": rel, "reason": "output_dir_invalid"})
                continue
            out_dir = _resolve(out_dir_raw)
            if not out_dir.exists():
                missing.append({"case_yaml": rel, "reason": "fixture_missing"})
                continue
            if any(not (out_dir / r).exists() for r in STANDARD_REQUIRED):
                missing.append({"case_yaml": rel, "reason": "output_dir_invalid"})
                continue
            resolved[split].append(case)
    return resolved, missing


# ---------------------------------------------------------------------------
# run one case with candidate Skill override
# ---------------------------------------------------------------------------
def _assertion_pass(assertions: list[dict], type_name: str) -> bool | None:
    seen = False
    ok = True
    for a in assertions or []:
        if a.get("type") == type_name:
            seen = True
            if not a.get("passed"):
                ok = False
    return ok if seen else None


def _run_case(case: dict) -> dict[str, Any]:
    """跑 pipeline（static_first=False 保持 offline 快速），抽取门禁所需信号。"""
    from framework import pipeline as pipeline_mod

    result = pipeline_mod.run_pipeline(case, static_first=False, dry_run=False)
    score = result.score_result or {}
    dims = score.get("dimensions") or {}
    assertions = result.assertions or []

    oc = _assertion_pass(assertions, "output_contract")
    if oc is None:
        oc = dims.get("output_contract") == PASS_DIMENSION_SCORE
    da = _assertion_pass(assertions, "data_authenticity")
    if da is None:
        da = dims.get("data_authenticity") == PASS_DIMENSION_SCORE

    gt = result.gt_eval or {}
    numeric_accuracy = gt.get("numeric_accuracy") if gt.get("status") == "success" else None

    tags = case.get("tags") or []
    is_abnormal = "abnormal" in tags or bool((case.get("expected_error") or {}).get("error_code"))

    return {
        "case_id": case.get("case_id", ""),
        "status": result.status,
        "weighted_score": score.get("weighted_score"),
        "dimensions": dims,
        "output_contract_pass": bool(oc),
        "data_authenticity_pass": bool(da),
        "numeric_accuracy": numeric_accuracy,
        "is_abnormal": is_abnormal,
        "abnormal_pass": dims.get("abnormal_handling"),
    }


# ---------------------------------------------------------------------------
# run_gate
# ---------------------------------------------------------------------------
def run_gate(
    patch: dict[str, Any],
    *,
    skillopt_config: dict[str, Any] | None = None,
    baseline_summary: dict[str, Any] | None = None,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """对单个 patch 跑 validation + regression 门禁，返回 GateResult dict。"""
    cfg = skillopt_config if skillopt_config is not None else load_skillopt_config()
    baseline = baseline_summary if baseline_summary is not None else load_baseline_summary()
    gate_rules = cfg.get("gate") or {}
    patch_cfg = cfg.get("patch") or {}
    dry_run_only = bool(patch_cfg.get("dry_run_only", True))
    baseline_version = patch_cfg.get("baseline_version", skill_patch.DEFAULT_BASELINE_VERSION)

    ws_root = Path(workspace_root) if workspace_root else None

    result: dict[str, Any] = {
        "patch_id": patch.get("patch_id", "<unknown>"),
        "accepted": False,
        "accept_type": "rejected",
        "evaluation_mode": "fixture_scores_only",
        "skill_dir_used": None,
        "validation_status": "skipped_no_cases",
        "missing_cases": [],
        "resolved_splits": {"train": [], "validation": [], "regression": []},
        "reasons": [],
        "score_diff": {},
        "patch_applied": False,
        "created_at": _now_iso(),
    }

    # 1. 静态白名单校验。
    ok, errs = skill_patch.validate_patch(patch)
    if not ok:
        result["reasons"] = [f"patch failed whitelist/schema check: {e}" for e in errs]
        _persist_rejection(patch, result)
        return result

    # 2. 解析 splits。
    resolved, missing = resolve_splits(cfg.get("splits") or {})
    result["missing_cases"] = missing
    result["resolved_splits"] = {k: [c.get("case_id", "") for c in v] for k, v in resolved.items()}

    # 3. apply patch -> candidate workspace（skill scope）。
    try:
        candidate = skill_patch.ensure_candidate_workspace(ws_root, baseline_version, force=True)
        if patch.get("target_scope") == "judge" and dry_run_only:
            # P0 dry-run：judge patch 不写生产 judge/，仅 candidate（无 judge 文件）→ 标记未 apply。
            result["reasons"].append("judge-scope patch not applied in P0 dry-run (candidate seeded from baseline)")
        else:
            skill_patch.apply_to_workspace(patch, candidate, baseline_version=baseline_version)
            result["patch_applied"] = True
    except Exception as exc:
        result["reasons"] = [f"apply_to_workspace failed: {exc}"]
        _persist_rejection(patch, result)
        return result

    result["skill_dir_used"] = str(candidate.resolve())

    # 4. 设置 Skill 路径覆盖，跑 cases，结束后恢复环境。
    prev = os.environ.get("SKILL_DIR_OVERRIDE")
    os.environ["SKILL_DIR_OVERRIDE"] = str(candidate.resolve())
    try:
        ran: dict[str, dict[str, Any]] = {}
        for split in ("train", "validation", "regression"):
            for case in resolved.get(split, []):
                cid = case.get("case_id", "")
                if cid not in ran:
                    ran[cid] = _run_case(case)
    finally:
        if prev is None:
            os.environ.pop("SKILL_DIR_OVERRIDE", None)
        else:
            os.environ["SKILL_DIR_OVERRIDE"] = prev

    # 5. validation_status（按配置数 vs 实际解析数判定）。
    val_ids = result["resolved_splits"].get("validation") or []
    configured_val = len((cfg.get("splits") or {}).get("validation") or [])
    if configured_val == 0 or len(val_ids) == 0:
        result["validation_status"] = "skipped_no_cases"
    elif len(val_ids) < configured_val:
        result["validation_status"] = "partial_missing"
    else:
        result["validation_status"] = "ran"

    # 6. 与 baseline 对比 + 门禁判定。
    bmap = _baseline_map(baseline)
    reasons: list[str] = []
    reg_ids = result["resolved_splits"].get("regression") or []
    score_diff: dict[str, Any] = {}

    for cid in reg_ids:
        run = ran.get(cid, {})
        cand_score = run.get("weighted_score")
        base = bmap.get(cid)
        base_score = base.get("weighted_score") if base else None
        score_diff[cid] = {"baseline": base_score, "candidate": cand_score}

        if gate_rules.get("require_output_contract_pass", True) and not run.get("output_contract_pass"):
            reasons.append(f"output_contract failed on {cid}")
        if gate_rules.get("require_data_authenticity_pass", True) and not run.get("data_authenticity_pass"):
            reasons.append(f"data_authenticity failed on {cid}")

        if base_score is not None and cand_score is not None:
            min_delta = float(gate_rules.get("min_weighted_score_vs_baseline", 0.0))
            if cand_score - base_score < min_delta:
                reasons.append(f"weighted_score regressed on {cid} (baseline={base_score}, candidate={cand_score})")
            base_na = base.get("dimensions", {}).get("financial_accuracy") if base else None
            cand_na = run.get("numeric_accuracy")
            if base_na is not None and cand_na is not None:
                min_na = float(gate_rules.get("min_numeric_accuracy_vs_baseline", 0.0))
                if float(cand_na) - float(base_na) < min_na:
                    reasons.append(f"numeric_accuracy regressed on {cid}")

        if gate_rules.get("require_no_abnormal_regression", True) and run.get("is_abnormal"):
            base_ab = base.get("dimensions", {}).get("abnormal_handling") if base else None
            cand_ab = run.get("abnormal_pass")
            if base_ab is not None and cand_ab is not None and float(cand_ab) < float(base_ab):
                reasons.append(f"abnormal_handling regressed on {cid}")

    # validation cases：也记录分数（require_improvement_on 为空时不强制）。
    for cid in val_ids:
        run = ran.get(cid, {})
        score_diff.setdefault(cid, {"baseline": bmap.get(cid, {}).get("weighted_score"),
                                    "candidate": run.get("weighted_score")})
    require_improve = gate_rules.get("require_improvement_on") or []
    if require_improve and result["validation_status"] == "ran":
        for dim in require_improve:
            improved = False
            for cid in val_ids:
                run = ran.get(cid, {})
                base = bmap.get(cid, {})
                cv = (run.get("dimensions") or {}).get(dim)
                bv = (base.get("dimensions") or {}).get(dim)
                if cv is not None and bv is not None and float(cv) > float(bv):
                    improved = True
            if not improved:
                reasons.append(f"no improvement on required dimension '{dim}' across validation split")

    result["score_diff"] = score_diff
    result["reasons"] = reasons

    if reasons:
        result["accepted"] = False
        result["accept_type"] = "rejected"
        _persist_rejection(patch, result)
    else:
        result["accepted"] = True
        # P0 fixture_scores_only：通过门禁、无回归，但未观察到分数提升 → no_regression_accepted。
        result["accept_type"] = "no_regression_accepted"

    # 7. 写 score_diff。
    OPT_DIR.mkdir(parents=True, exist_ok=True)
    SCORE_DIFF_PATH.write_text(json.dumps(score_diff, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _persist_rejection(patch: dict[str, Any], result: dict[str, Any]) -> None:
    REJECTED_BUFFER.parent.mkdir(parents=True, exist_ok=True)
    buffer: list[dict] = []
    if REJECTED_BUFFER.exists():
        try:
            buffer = json.loads(REJECTED_BUFFER.read_text(encoding="utf-8"))
            if not isinstance(buffer, list):
                buffer = []
        except Exception:
            buffer = []
    buffer = [b for b in buffer if b.get("patch_id") != patch.get("patch_id")]
    buffer.append({
        "patch_id": patch.get("patch_id"),
        "target_scope": patch.get("target_scope"),
        "target_file": patch.get("target_file"),
        "reasons": result.get("reasons", []),
        "rejected_at": _now_iso(),
    })
    REJECTED_BUFFER.write_text(json.dumps(buffer, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Step 6: 报告写入（仍在本模块内，避免新增第 3 个 Python 文件）
# ---------------------------------------------------------------------------
def _label_for(patch: dict[str, Any]) -> str:
    pid = patch.get("patch_id", "patch")
    return pid[len("patch_v1_"):] if pid.startswith("patch_v1_") else pid


def write_iteration_report(patch: dict[str, Any], result: dict[str, Any]) -> Path:
    OPT_DIR.mkdir(parents=True, exist_ok=True)
    label = _label_for(patch)
    accepted = result.get("accepted")
    lines = [
        f"## skill_v0_baseline -> skill_v1_{label}",
        "",
        "> P0 说明：若 accept_type=no_regression_accepted，表示 patch 未造成回归且 gate 通过，",
        "> **不代表**真实解析能力已提升。能力提升需 patch 被 postprocess 消费且在 validation case 上可量化提高。",
        "",
        "### 修改了什么",
        f"- patch_id: `{patch.get('patch_id')}`",
        f"- target_scope: `{patch.get('target_scope')}`",
        f"- target_file: `{patch.get('target_file')}`",
        f"- edit_type: `{patch.get('edit_type')}`",
        f"- change 摘要: {json.dumps(patch.get('change', {}), ensure_ascii=False)}",
        "",
        "### skill_dir_used",
        f"- `{result.get('skill_dir_used')}`",
        "",
        "### evaluation_mode",
        f"- `{result.get('evaluation_mode')}`"
        + ("（fixture backend 不 re-invoke Skill，只对比已有 fixture 分数）"
           if result.get("evaluation_mode") == "fixture_scores_only" else ""),
        "",
        "### 为什么修改",
        f"- failure_trace 来源: `{patch.get('source_trace', 'n/a')}`；reason: {patch.get('reason')}",
        "",
        "### accept_type",
        f"- `{result.get('accept_type')}`",
        "",
        "### validation_status",
        f"- `{result.get('validation_status')}`",
        "",
        "### resolved_splits",
        f"- train: {result.get('resolved_splits', {}).get('train')}",
        f"- validation: {result.get('resolved_splits', {}).get('validation')}",
        f"- regression: {result.get('resolved_splits', {}).get('regression')}",
        "",
        "### missing_cases",
    ]
    missing = result.get("missing_cases") or []
    if missing:
        for m in missing:
            lines.append(f"- `{m['case_yaml']}` -> {m['reason']}")
    else:
        lines.append("- 无")
    lines += ["", "### 哪些 case 提升 / 未提升"]
    sd = result.get("score_diff") or {}
    if result.get("validation_status") == "skipped_no_cases":
        lines.append("- validation split 为空：不宣称泛化能力提升，仅证明 gate 机制可运行。")
    if sd:
        lines.append("")
        lines.append("| case | baseline | candidate |")
        lines.append("|------|----------|-----------|")
        for cid, d in sd.items():
            lines.append(f"| {cid} | {d.get('baseline')} | {d.get('candidate')} |")
    else:
        lines.append("- N/A")
    lines += [
        "",
        "### 是否回归",
        ("- 无回归" if accepted else "- 存在问题：" + "; ".join(result.get("reasons", []))),
        "",
        "### 是否通过 validation gate",
        f"- accepted: {accepted}",
        "",
        "---",
        "",
    ]
    # 累加写入（保留历史迭代）。
    header = "# SkillOpt Iterations\n\n" if not ITERATIONS_MD.exists() else ""
    with ITERATIONS_MD.open("a", encoding="utf-8") as fh:
        if header:
            fh.write(header)
        fh.write("\n".join(lines))
    return ITERATIONS_MD


def _append_list_md(path: Path, title: str, patch: dict[str, Any], result: dict[str, Any]) -> None:
    line = (f"- `{patch.get('patch_id')}` | scope={patch.get('target_scope')} | "
            f"file={patch.get('target_file')} | accept_type={result.get('accept_type')} | "
            f"reasons={result.get('reasons') or 'none'} | at={result.get('created_at')}")
    header = f"# {title}\n\n" if not path.exists() else ""
    with path.open("a", encoding="utf-8") as fh:
        if header:
            fh.write(header)
        fh.write(line + "\n")


def finalize(patch: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Step 6：accept 时 snapshot 版本；写迭代报告与 accepted/rejected 清单。"""
    write_iteration_report(patch, result)
    if result.get("accepted"):
        _append_list_md(ACCEPTED_MD, "Accepted Patches", patch, result)
        try:
            dest = skill_patch.snapshot_version(_label_for(patch))
            result["snapshot_path"] = str(dest)
        except Exception as exc:
            LOG.warning("snapshot failed: %s", exc)
    else:
        _append_list_md(REJECTED_MD, "Rejected Patches", patch, result)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m optimizer.gate")
    parser.add_argument("--patch", metavar="JSON", required=True, help="proposed patch JSON 路径")
    parser.add_argument("--no-finalize", action="store_true", help="只跑门禁，不写报告 / 不 snapshot")
    args = parser.parse_args(argv)

    patch_path = _resolve(args.patch)
    patch = json.loads(patch_path.read_text(encoding="utf-8"))
    result = run_gate(patch)
    if not args.no_finalize:
        result = finalize(patch, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("accepted") else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
