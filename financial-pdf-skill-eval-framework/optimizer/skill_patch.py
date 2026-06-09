"""optimizer.skill_patch —— SkillOpt dry-run patch 提案 + 临时 workspace 应用 + 版本快照（三合一）。

职责（单文件，对应 README §7 的 proposer + applier + version_manager）：

    propose_patches(failure_traces)  读 failure_trace JSON → 规则模板 patch（P0 不调 LLM）
    apply_to_workspace(patch, ...)   从 skill_v0_baseline 复制 Skill 包到 candidate/，再 apply
    snapshot_version(label, ...)     gate 通过后把 candidate/ 复制到 skill_versions/skill_v1_<label>/

红线：
    - 不 touch 生产 ``skills/financial-pdf-parse-doubao-eval/`` 根目录（仅 skill_versions/ 子目录可新增快照）。
    - patch 必须用 ``target_scope`` + 相对 ``target_file``；禁止 repo 级 / 绝对 / '..' 路径。
    - judge-scope patch 在 P0 dry-run 下默认不 apply 到生产 ``judge/``。
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from framework.context import FRAMEWORK_ROOT, REPO_ROOT
from framework.logger import get_logger

LOG = get_logger("skill_patch")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SKILL_PKG_DIR = REPO_ROOT / "skills" / "financial-pdf-parse-doubao-eval"
SKILL_VERSIONS_DIR = SKILL_PKG_DIR / "skill_versions"
TRACES_DIR = FRAMEWORK_ROOT / "reports" / "traces"
PROPOSED_DIR = FRAMEWORK_ROOT / "reports" / "optimization" / "proposed_patches"
SCHEMA_PATH = Path(__file__).resolve().parent / "patch_schema.json"
JUDGE_DIR = FRAMEWORK_ROOT / "judge"

DEFAULT_WORKSPACE_ROOT = FRAMEWORK_ROOT / ".skillopt_workspace"
DEFAULT_CANDIDATE_DIR = DEFAULT_WORKSPACE_ROOT / "skill_candidate"
DEFAULT_BASELINE_VERSION = "skill_v0_baseline"


# ---------------------------------------------------------------------------
# Patch templates（failure_trace.suggested_targets -> 结构化 patch）
# ---------------------------------------------------------------------------
_PATCH_TEMPLATES: dict[str, dict[str, Any]] = {
    "multi_header_table_rebuilder": {
        "patch_id": "patch_v1_multi_header",
        "target_scope": "skill",
        "target_file": "rules/multi_header_table_rebuilder.yaml",
        "edit_type": "add",
        "reason": "failure_trace 显示多级日期表头未展开为稳定二维结构，period 列识别失败",
        "change": {
            "rule_id": "multi_header_table_rebuilder",
            "description": "当表格前两行均包含日期/期间字段时，合并为多级表头并展开 period 列",
            "trigger": "table_top_rows_contain_period_tokens",
            "action": "merge_into_multilevel_header",
        },
        "expected_improvement": ["table_structure", "financial_accuracy"],
        "risk": "可能误合并正文中的日期行",
    },
    "period_column_normalizer": {
        "patch_id": "patch_v1_period_column",
        "target_scope": "skill",
        "target_file": "rules/period_column_normalizer.yaml",
        "edit_type": "add",
        "reason": "failure_trace 显示 period 列依赖列名字符串而非独立表头层级",
        "change": {
            "rule_id": "period_column_normalizer",
            "description": "把列名中的期间字符串归一化为独立 period 维度",
            "trigger": "period_token_in_column_name",
            "action": "promote_period_to_dimension",
        },
        "expected_improvement": ["table_structure"],
        "risk": "对非期间列误判风险",
    },
    "reading_order_resolver": {
        "patch_id": "patch_v1_reading_order",
        "target_scope": "skill",
        "target_file": "rules/reading_order_resolver.yaml",
        "edit_type": "add",
        "reason": "failure_trace 显示跨表合并报表阅读连续性需人工拼接",
        "change": {
            "rule_id": "reading_order_resolver",
            "description": "对被拆分的合并报表子表，按标题语义恢复阅读顺序",
            "trigger": "split_consolidated_statement",
            "action": "stitch_subtables_by_title",
        },
        "expected_improvement": ["reading_order", "table_structure"],
        "risk": "标题相似时可能错误拼接",
    },
    "metric_extraction_recall": {
        "patch_id": "patch_v1_metric_recall",
        "target_scope": "skill",
        "target_file": "rules/metric_extraction_recall.yaml",
        "edit_type": "add",
        "reason": "failure_trace 显示关键财务指标缺失（missing_metric）",
        "change": {
            "rule_id": "metric_extraction_recall",
            "description": "扩展指标别名表以提升关键财务指标抽取召回",
            "trigger": "known_metric_alias_missed",
            "action": "expand_metric_alias_table",
        },
        "expected_improvement": ["financial_accuracy"],
        "risk": "别名过宽可能误抽取",
    },
}


def _generic_template(target: str) -> dict[str, Any]:
    """未知 suggested_target 的兜底 skill 规则 patch（不造假数据，仅模板占位）。"""
    safe = "".join(ch if (ch.isalnum() or ch in "_-") else "_" for ch in target) or "rule"
    return {
        "patch_id": f"patch_v1_{safe}",
        "target_scope": "skill",
        "target_file": f"rules/{safe}.yaml",
        "edit_type": "add",
        "reason": f"failure_trace.suggested_targets 提出优化目标 {target}",
        "change": {
            "rule_id": safe,
            "description": f"针对 {target} 的占位规则，待人工细化",
        },
        "expected_improvement": ["table_structure"],
        "risk": "占位规则，需人工确认",
    }


# ---------------------------------------------------------------------------
# Validation（schema + 路径安全）
# ---------------------------------------------------------------------------
def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def is_safe_relpath(target_file: str) -> bool:
    """target_file 必须为相对路径，且不含 '..'、不为绝对路径、无盘符。"""
    if not target_file or not isinstance(target_file, str):
        return False
    p = Path(target_file)
    if p.is_absolute():
        return False
    # Windows 盘符 / UNC 检测。
    if p.drive or target_file.startswith(("/", "\\")):
        return False
    return ".." not in p.parts


def validate_patch(patch: dict[str, Any]) -> tuple[bool, list[str]]:
    """schema 校验 + target_scope/target_file 白名单（静态）。返回 (ok, errors)。"""
    errors: list[str] = []
    try:
        import jsonschema

        jsonschema.validate(patch, _load_schema())
    except ModuleNotFoundError:
        # 无 jsonschema 时退化为手工必填项检查（offline 兜底）。
        required = ["patch_id", "target_scope", "target_file", "edit_type", "reason", "change"]
        for k in required:
            if k not in patch:
                errors.append(f"missing required field: {k}")
        if patch.get("target_scope") not in {"skill", "judge"}:
            errors.append("target_scope must be one of {skill, judge}")
        if patch.get("edit_type") not in {"add", "replace", "delete"}:
            errors.append("edit_type must be one of {add, replace, delete}")
    except Exception as exc:  # jsonschema.ValidationError 等
        errors.append(f"schema invalid: {getattr(exc, 'message', str(exc))}")

    tf = patch.get("target_file", "")
    if not is_safe_relpath(tf):
        errors.append(f"unsafe target_file (absolute / '..' / drive not allowed): {tf!r}")
    return (not errors), errors


# ---------------------------------------------------------------------------
# propose
# ---------------------------------------------------------------------------
def load_failure_traces(traces_dir: Path | None = None) -> list[dict[str, Any]]:
    d = traces_dir or TRACES_DIR
    out: list[dict[str, Any]] = []
    if not d.exists():
        return out
    for f in sorted(d.glob("*_failure_trace.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as exc:  # pragma: no cover - corrupt artifact
            LOG.warning("skip unreadable trace %s: %s", f, exc)
    return out


def _patch_for_target(target: str) -> dict[str, Any]:
    tmpl = _PATCH_TEMPLATES.get(target)
    return dict(tmpl) if tmpl else _generic_template(target)


def propose_patches(failure_traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """读 failure_trace（JSON，绝不读 Markdown）→ 每个失败模式 1 条模板 patch。

    去重保序：按 suggested_targets 首次出现顺序生成；记录来源 case_id。
    输出写入 reports/optimization/proposed_patches/<patch_id>.json。
    """
    targets: list[str] = []
    target_source: dict[str, str] = {}
    for tr in failure_traces:
        case_id = tr.get("case_id", "")
        for t in tr.get("suggested_targets") or []:
            if t not in targets:
                targets.append(t)
                target_source[t] = case_id

    PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    proposed: list[dict[str, Any]] = []
    for t in targets:
        patch = _patch_for_target(t)
        patch["source_trace"] = target_source.get(t, "")
        ok, errs = validate_patch(patch)
        if not ok:
            LOG.warning("generated patch for %s failed validation: %s", t, errs)
            continue
        out_path = PROPOSED_DIR / f"{patch['patch_id']}.json"
        out_path.write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding="utf-8")
        LOG.info("proposed %s -> %s", patch["patch_id"], out_path)
        proposed.append(patch)
    return proposed


# ---------------------------------------------------------------------------
# apply to candidate workspace
# ---------------------------------------------------------------------------
def baseline_version_dir(version: str = DEFAULT_BASELINE_VERSION) -> Path:
    return SKILL_VERSIONS_DIR / version


def ensure_candidate_workspace(
    workspace_root: Path | None = None,
    baseline_version: str = DEFAULT_BASELINE_VERSION,
    *,
    force: bool = False,
) -> Path:
    """确保 candidate workspace 存在；不存在（或 force）时从 skill_v0_baseline 复制整个 Skill 包。"""
    candidate = Path(workspace_root) if workspace_root else DEFAULT_CANDIDATE_DIR
    if force and candidate.exists():
        shutil.rmtree(candidate)
    if not candidate.exists():
        src = baseline_version_dir(baseline_version)
        if not src.exists():
            raise FileNotFoundError(f"baseline skill version missing: {src}")
        candidate.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, candidate)
        LOG.info("seeded candidate workspace from %s -> %s", src, candidate)
    return candidate


def _resolve_target_root(target_scope: str, candidate: Path) -> Path:
    if target_scope == "skill":
        return candidate
    if target_scope == "judge":
        return JUDGE_DIR
    raise ValueError(f"unknown target_scope: {target_scope}")


def _write_change(target: Path, patch: dict[str, Any]) -> None:
    change = patch.get("change") or {}
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = target.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        import yaml

        target.write_text(yaml.safe_dump(change, allow_unicode=True, sort_keys=False), encoding="utf-8")
    elif suffix in {".md", ".markdown"}:
        text = change.get("text")
        if text is None:
            text = json.dumps(change, ensure_ascii=False, indent=2)
        target.write_text(text, encoding="utf-8")
    else:
        target.write_text(json.dumps(change, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_to_workspace(
    patch: dict[str, Any],
    workspace_root: Path | None = None,
    *,
    baseline_version: str = DEFAULT_BASELINE_VERSION,
    allow_judge_apply: bool = False,
) -> Path:
    """把 patch 应用到 candidate workspace（skill scope）或 judge/（仅显式允许时）。

    返回被写/删的 target 文件绝对路径。生产 Skill 根目录绝不被改动。
    """
    ok, errs = validate_patch(patch)
    if not ok:
        raise ValueError(f"invalid patch {patch.get('patch_id')}: {errs}")

    candidate = ensure_candidate_workspace(workspace_root, baseline_version)
    scope = patch["target_scope"]
    if scope == "judge" and not allow_judge_apply:
        # P0 dry-run：judge-scope patch 不写生产 judge/，避免污染评测器配置。
        raise PermissionError(
            "judge-scope patch apply is disabled in P0 dry-run (set allow_judge_apply=True to override)"
        )

    root = _resolve_target_root(scope, candidate)
    target = (root / patch["target_file"]).resolve()
    # 防御：apply 后的 target 必须仍位于其 scope 根目录内。
    if root.resolve() not in target.parents and target != root.resolve():
        raise ValueError(f"resolved target escapes scope root: {target}")

    edit = patch["edit_type"]
    if edit in {"add", "replace"}:
        _write_change(target, patch)
    elif edit == "delete":
        if target.exists():
            target.unlink()
    LOG.info("applied %s (%s) -> %s", patch.get("patch_id"), edit, target)
    return target


# ---------------------------------------------------------------------------
# snapshot version（仅 gate 通过后调用）
# ---------------------------------------------------------------------------
def snapshot_version(label: str, workspace_path: Path | None = None) -> Path:
    """把 candidate workspace 复制为 skill_versions/skill_v1_<label>/（不覆盖 skill 根目录）。"""
    candidate = Path(workspace_path) if workspace_path else DEFAULT_CANDIDATE_DIR
    if not candidate.exists():
        raise FileNotFoundError(f"candidate workspace missing: {candidate}")
    dest = SKILL_VERSIONS_DIR / f"skill_v1_{label}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(candidate, dest, dirs_exist_ok=True)
    LOG.info("snapshotted candidate -> %s", dest)
    return dest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m optimizer.skill_patch")
    parser.add_argument("--propose", action="store_true", help="读 failure_trace 生成 dry-run patch 提案")
    parser.add_argument("--traces-dir", metavar="DIR", help="failure_trace 目录（默认 reports/traces）")
    args = parser.parse_args(argv)

    if args.propose:
        traces = load_failure_traces(Path(args.traces_dir) if args.traces_dir else None)
        if not traces:
            LOG.warning("no failure_trace found under %s", args.traces_dir or TRACES_DIR)
        proposed = propose_patches(traces)
        print(json.dumps(
            {"proposed_count": len(proposed), "patch_ids": [p["patch_id"] for p in proposed],
             "out_dir": str(PROPOSED_DIR)},
            ensure_ascii=False, indent=2,
        ))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
