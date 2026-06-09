"""Thin wrapper that exposes report_collector functions under evaluation.* for convenience."""
from framework.report_collector import (  # noqa: F401
    summarize_case,
    write_summary_markdown,
    write_failure_cases_markdown,
    write_final_project_report,
    collect_summaries_from_manifest,
)
