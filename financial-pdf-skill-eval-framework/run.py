#!/usr/bin/env python3
"""Entrypoint for the financial-pdf-parse-doubao-eval evaluation framework.

This CLI does NOT run the Skill by default. It can:
- import existing real_las outputs as fixtures
- run a single YAML case via the Skill (when explicitly allowed)
- aggregate Markdown summary / failure / final reports
- run pytest with marker filtering
- invoke the Skill's OpenClaw evidence collector

real_las and real_openclaw are gated by env vars and YAML opt-ins.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from framework.bootstrap import FRAMEWORK_ROOT  # noqa: F401
from framework import case_loader, pipeline as pipeline_mod, report_collector, skill_invoker
from framework.assertion_engine import run_validations
from framework.context import load_config
from framework.logger import get_logger
from framework.output_contract import read_quality_checks, read_run_meta

LOG = get_logger("run")


STANDARD_REQUIRED = [
    "raw/parsed.md",
    "normalized/normalized_tables.json",
    "normalized/financial_summary.json",
    "evaluation/quality_checks.json",
    "meta/run_meta.json",
]


def _looks_like_case_dir(p: Path) -> bool:
    return all((p / r).exists() for r in STANDARD_REQUIRED)


def cmd_import_real_outputs(source: str) -> int:
    src = Path(source).resolve()
    if not src.exists():
        LOG.error("source not found: %s", src)
        return 2

    work_dir = src
    if src.is_file() and src.suffix.lower() == ".zip":
        extract_dir = FRAMEWORK_ROOT / "data" / "real_las_outputs" / "_unzip"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(src) as z:
            z.extractall(extract_dir)
        work_dir = extract_dir
        LOG.info("extracted %s to %s", src, extract_dir)

    target_dir = FRAMEWORK_ROOT / "data" / "real_las_outputs"
    target_dir.mkdir(parents=True, exist_ok=True)

    discovered: list[dict] = []
    for path in [work_dir, *work_dir.rglob("*")]:
        if not path.is_dir():
            continue
        if _looks_like_case_dir(path):
            case_id = path.name
            dest = target_dir / case_id
            if dest.resolve() != path.resolve():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(path, dest)
                LOG.info("imported %s -> %s", path, dest)
            else:
                LOG.info("kept in place: %s", dest)
            meta = read_run_meta(dest)
            qc = read_quality_checks(dest)
            stats = qc.get("table_statistics") or {}
            mstats = qc.get("metric_statistics") or {}
            discovered.append({
                "case_id": f"{case_id}_real_las_fixture",
                "source_output_dir": str(Path("data/real_las_outputs") / case_id).replace("\\", "/"),
                "execution_backend": meta.get("execution_backend") or "real_las",
                "output_source": meta.get("output_source") or "real_las",
                "is_synthetic": bool(meta.get("is_synthetic", False)),
                "count_as_real_evaluation": bool(meta.get("count_as_real_evaluation", True)),
                "raw_table_count": stats.get("raw_table_count"),
                "financial_table_count": stats.get("financial_table_count"),
                "metric_record_count": mstats.get("metric_record_count"),
                "has_ground_truth": False,
            })

    if not discovered:
        LOG.warning("no standard-profile case directories found under %s", work_dir)
    manifest = FRAMEWORK_ROOT / "configs" / "dataset_manifest.yaml"
    import yaml
    data = {"real_las_fixtures": discovered}
    manifest.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    LOG.info("wrote %s with %d fixtures", manifest, len(discovered))
    return 0


def cmd_run_case(case_path: str) -> int:
    case = case_loader.load_case(case_path)
    LOG.info("running case %s (backend=%s)", case["case_id"], case.get("backend"))
    invocation = skill_invoker.invoke(case)
    LOG.info("invocation result: %s", invocation.get("status"))
    validations = run_validations(case, invocation)
    summary = report_collector.summarize_case(case, invocation, validations)
    print(json.dumps({"invocation": invocation, "validations": validations, "summary": summary}, ensure_ascii=False, indent=2))
    return 0 if invocation.get("status") in {"success", "skipped", "fixture", "dry_run"} else 1


def cmd_run_cases_dir(cases_dir: str) -> int:
    cases = case_loader.load_cases_from_dir(cases_dir, include_multi=False)
    if not cases:
        LOG.warning("no cases found under %s", cases_dir)
        return 0
    summaries = []
    failed = 0
    for case in cases:
        try:
            inv = skill_invoker.invoke(case)
            v = run_validations(case, inv)
            s = report_collector.summarize_case(case, inv, v)
            summaries.append(s)
            if any(not x.get("passed") for x in v):
                failed += 1
        except Exception as e:
            LOG.exception("case %s crashed: %s", case.get("case_id"), e)
            failed += 1
    report_collector.write_summary_markdown(summaries, FRAMEWORK_ROOT / "reports" / "markdown" / "evaluation_summary.md")
    report_collector.write_failure_cases_markdown(summaries, FRAMEWORK_ROOT / "reports" / "markdown" / "failure_cases.md")
    return 0 if failed == 0 else 1


def cmd_pytest_mark(mark: str) -> int:
    cmd = [sys.executable, "-m", "pytest", "-q", "-m", mark]
    LOG.info("pytest cmd: %s", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(FRAMEWORK_ROOT))


def cmd_summary() -> int:
    summaries = report_collector.collect_summaries_from_manifest()
    report_collector.write_summary_markdown(summaries, FRAMEWORK_ROOT / "reports" / "markdown" / "evaluation_summary.md")
    report_collector.write_failure_cases_markdown(summaries, FRAMEWORK_ROOT / "reports" / "markdown" / "failure_cases.md")
    LOG.info("wrote summary with %d cases", len(summaries))
    return 0


def cmd_fixture_summary() -> int:
    target_dir = FRAMEWORK_ROOT / "data" / "real_las_outputs"
    rows = []
    for sub in sorted(target_dir.iterdir()) if target_dir.exists() else []:
        if not sub.is_dir() or not _looks_like_case_dir(sub):
            continue
        meta = read_run_meta(sub)
        qc = read_quality_checks(sub)
        rows.append({
            "case_id": sub.name,
            "execution_backend": meta.get("execution_backend"),
            "table_statistics": qc.get("table_statistics"),
            "metric_statistics": qc.get("metric_statistics"),
        })
    out = FRAMEWORK_ROOT / "reports" / "markdown" / "fixture_summary.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Fixture Summary", ""]
    for r in rows:
        lines.append(f"## {r['case_id']}")
        lines.append(f"- execution_backend: {r['execution_backend']}")
        lines.append(f"- table_statistics: {r['table_statistics']}")
        lines.append(f"- metric_statistics: {r['metric_statistics']}")
        lines.append("")
    if not rows:
        lines.append("_No fixtures imported yet. Run `python run.py --import-real-outputs <path>`._")
    out.write_text("\n".join(lines), encoding="utf-8")
    LOG.info("wrote %s with %d fixtures", out, len(rows))
    return 0


def cmd_collect_openclaw_evidence() -> int:
    cfg = load_config()
    script = cfg.skill.evidence_script
    if not script.exists():
        LOG.error("evidence script missing: %s", script)
        return 2
    out_path = FRAMEWORK_ROOT / "reports" / "markdown" / "openclaw_invocation_log.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    outputs_dir = FRAMEWORK_ROOT / "data" / "real_las_outputs"
    cmd = [sys.executable, str(script), "--skill-dir", str(cfg.skill.path), "--outputs-dir", str(outputs_dir), "--output", str(out_path)]
    LOG.info("evidence cmd: %s", " ".join(cmd))
    rc = subprocess.call(cmd)
    # Always append framework's disclaimer in case the Skill didn't
    if out_path.exists():
        text = out_path.read_text(encoding="utf-8")
        marker = "## Framework disclaimer"
        if marker not in text:
            text += (
                f"\n\n{marker}\n\n"
                "- `real_las` is direct LAS / lasutil invocation. It is NOT `real_openclaw`.\n"
                "- `real_openclaw` backend has not been verified in this submission; tests skip it by default.\n"
            )
            out_path.write_text(text, encoding="utf-8")
    return rc


def cmd_generate_final_report() -> int:
    summaries = report_collector.collect_summaries_from_manifest()
    out = FRAMEWORK_ROOT / "reports" / "final" / "final_project_report.md"
    report_collector.write_final_project_report(summaries, out)
    LOG.info("wrote %s", out)
    return 0


def cmd_static_only(output: str | None = None) -> int:
    from static_tests.run_static import run_all
    report = run_all()
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    out_path = Path(output) if output else FRAMEWORK_ROOT / "reports" / "static" / "static.json"
    if not out_path.is_absolute():
        out_path = (FRAMEWORK_ROOT / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    LOG.info("wrote %s (overall_pass=%s)", out_path, report["overall_pass"])
    return 0 if report["overall_pass"] else 1


def _load_cases_arg(cases_arg: str) -> list[dict]:
    p = Path(cases_arg)
    if not p.is_absolute():
        p = (FRAMEWORK_ROOT / p).resolve()
    if p.is_dir():
        return case_loader.load_cases_from_dir(p, include_multi=False)
    if not p.exists():
        raise FileNotFoundError(p)
    import yaml
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if isinstance(data, dict) and "cases" in data:
        return case_loader.load_abnormal_cases(p)
    return [case_loader.load_case(p)]


def cmd_pipeline(cases_arg: str, backend: str | None, dry_run: bool, static_first: bool) -> int:
    cases = _load_cases_arg(cases_arg)
    if not cases:
        LOG.warning("no cases found at %s", cases_arg)
        return 0
    if backend:
        for c in cases:
            c["backend"] = backend

    summaries: list[dict] = []
    failed_count = 0
    skipped_count = 0
    for case in cases:
        try:
            result = pipeline_mod.run_pipeline(case, static_first=static_first, dry_run=dry_run)
        except Exception as e:
            LOG.exception("pipeline crashed for %s: %s", case.get("case_id"), e)
            failed_count += 1
            continue
        print(json.dumps({
            "case_id": result.case_id,
            "status": result.status,
            "weighted_score": (result.score_result or {}).get("weighted_score"),
            "level": (result.score_result or {}).get("level"),
            "stages": [{"name": s.name, "status": s.status} for s in result.stages],
        }, ensure_ascii=False, indent=2))
        if result.status == "failed":
            failed_count += 1
        elif result.status == "skipped":
            skipped_count += 1
        try:
            summary = report_collector.summarize_case(case, result.invocation or {}, result.assertions or [])
            summaries.append(summary)
        except Exception as e:
            LOG.warning("summary failed for %s: %s", case.get("case_id"), e)
        # Emit SkillOpt-facing failure_trace (reads score/judge/gt artifacts from disk).
        if result.output_dir is not None:
            try:
                from optimizer import failure_trace
                ft = failure_trace.run_for_case(case, result.assertions or [])
                LOG.info("wrote %s", ft["trace_path"])
            except Exception as e:
                LOG.warning("failure_trace failed for %s: %s", case.get("case_id"), e)

    if summaries:
        report_collector.write_summary_markdown(summaries, FRAMEWORK_ROOT / "reports" / "markdown" / "evaluation_summary.md")
        report_collector.write_failure_cases_markdown(summaries, FRAMEWORK_ROOT / "reports" / "markdown" / "failure_cases.md")
        report_collector.write_score_summary_markdown(summaries, FRAMEWORK_ROOT / "reports" / "markdown" / "score_summary.md")

    LOG.info("pipeline done: total=%d failed=%d skipped=%d", len(cases), failed_count, skipped_count)
    return 0 if failed_count == 0 else 1


def cmd_build_dashboard_bundle() -> int:
    """仅读盘聚合产物，生成 reports/dashboard/dashboard_bundle.json。

    纯读盘：不触发任何评估、推理、pipeline、Skill 调用或 patch gate。
    """
    from framework import dashboard_bundle

    bundle = dashboard_bundle.build_dashboard_bundle()
    path = bundle.get("_bundle_path")
    cases = bundle.get("cases") or []
    print(f"Dashboard bundle 已生成：{path}")
    print(f"包含 case 数量：{len(cases)}")
    for c in cases:
        print(f"  - {c.get('case_id')} (missing_files={len(c.get('missing_files') or [])})")
    LOG.info("wrote %s with %d cases", path, len(cases))
    return 0


def cmd_serve_dashboard() -> int:
    """启动 Streamlit Dashboard（streamlit run dashboard/streamlit_app.py）。"""
    app_path = FRAMEWORK_ROOT / "dashboard" / "streamlit_app.py"
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print("未安装 Streamlit。请先安装展示依赖：")
        print("    pip install -r requirements-dashboard.txt")
        return 2
    # 启动前确保 bundle 存在（仅读盘生成，不跑真实 LAS / OpenClaw）。
    bundle_path = FRAMEWORK_ROOT / "reports" / "dashboard" / "dashboard_bundle.json"
    if not bundle_path.exists():
        LOG.info("dashboard bundle 不存在，先生成：%s", bundle_path)
        cmd_build_dashboard_bundle()
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    LOG.info("serve dashboard: %s", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(FRAMEWORK_ROOT))


def cmd_generate_report() -> int:
    summaries = report_collector.collect_summaries_from_manifest()
    report_collector.write_summary_markdown(summaries, FRAMEWORK_ROOT / "reports" / "markdown" / "evaluation_summary.md")
    report_collector.write_failure_cases_markdown(summaries, FRAMEWORK_ROOT / "reports" / "markdown" / "failure_cases.md")
    report_collector.write_score_summary_markdown(summaries, FRAMEWORK_ROOT / "reports" / "markdown" / "score_summary.md")
    report_collector.write_final_project_report(summaries, FRAMEWORK_ROOT / "reports" / "final" / "final_project_report.md")
    LOG.info("regenerated all reports (%d cases)", len(summaries))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run.py", description="financial-pdf-parse-doubao-eval evaluation framework CLI")
    p.add_argument("--import-real-outputs", metavar="PATH", help="Import a directory or zip of real_las outputs as fixtures")
    p.add_argument("--case", metavar="YAML", help="Run a single YAML case (legacy invoker)")
    p.add_argument("--cases-dir", metavar="DIR", help="Run every single-case YAML in a directory (legacy invoker)")
    p.add_argument("--mark", metavar="MARK", help="Run pytest with -m <MARK>")
    p.add_argument("--summary", action="store_true", help="Write reports/markdown/evaluation_summary.md")
    p.add_argument("--fixture-summary", action="store_true", help="Write reports/markdown/fixture_summary.md from data/real_las_outputs")
    p.add_argument("--collect-openclaw-evidence", action="store_true", help="Invoke Skill's evidence collector")
    p.add_argument("--generate-final-report", action="store_true", help="Write reports/final/final_project_report.md")
    # P0 additions
    p.add_argument("--static-only", action="store_true", help="Run static_tests/ checks only and print JSON")
    p.add_argument("--static-output", metavar="PATH", help="Optional output file for --static-only JSON")
    p.add_argument("--pipeline", action="store_true", help="Run P0 pipeline on --cases input")
    p.add_argument("--cases", metavar="PATH", help="Cases YAML file or directory for --pipeline")
    p.add_argument("--backend", metavar="BACKEND", help="Override backend for --pipeline (fixture / official_output_mock / real_las)")
    p.add_argument("--dry-run", action="store_true", help="dry-run skill invocation in --pipeline")
    p.add_argument("--no-static-first", action="store_true", help="Skip static_tests in --pipeline")
    p.add_argument("--generate-report", action="store_true", help="Regenerate all Markdown reports including score_summary")
    # 展示 Dashboard（只读）
    p.add_argument("--build-dashboard-bundle", action="store_true", help="仅读盘聚合产物，写入 reports/dashboard/dashboard_bundle.json")
    p.add_argument("--serve-dashboard", action="store_true", help="启动 Streamlit 展示 Dashboard（streamlit run dashboard/streamlit_app.py）")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.import_real_outputs:
        return cmd_import_real_outputs(args.import_real_outputs)
    if args.static_only:
        return cmd_static_only(args.static_output)
    if args.pipeline:
        if not args.cases:
            parser.error("--pipeline requires --cases <yaml-file-or-dir>")
        return cmd_pipeline(
            args.cases,
            backend=args.backend,
            dry_run=args.dry_run,
            static_first=not args.no_static_first,
        )
    if args.case:
        return cmd_run_case(args.case)
    if args.cases_dir:
        return cmd_run_cases_dir(args.cases_dir)
    if args.mark:
        return cmd_pytest_mark(args.mark)
    if args.summary:
        return cmd_summary()
    if args.fixture_summary:
        return cmd_fixture_summary()
    if args.collect_openclaw_evidence:
        return cmd_collect_openclaw_evidence()
    if args.generate_final_report:
        return cmd_generate_final_report()
    if args.generate_report:
        return cmd_generate_report()
    if args.build_dashboard_bundle:
        return cmd_build_dashboard_bundle()
    if args.serve_dashboard:
        return cmd_serve_dashboard()
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
