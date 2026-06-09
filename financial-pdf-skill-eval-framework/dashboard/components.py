"""可复用的 Streamlit 渲染组件（只读评测 Dashboard）。

所有数值（weighted_score / level / Judge 分数 / trace 等）均来自传入的
bundle 数据，组件本身不硬编码任何业务分数。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


# P0 六维（与 framework/report_collector.SCORE_DIMENSIONS 对齐）。
SCORE_DIMENSIONS = (
    "output_contract",
    "data_authenticity",
    "table_structure",
    "financial_accuracy",
    "abnormal_handling",
    "cost_performance",
)

DIMENSION_LABELS = {
    "output_contract": "输出契约",
    "data_authenticity": "数据真实性",
    "table_structure": "表格结构",
    "financial_accuracy": "财务准确率",
    "abnormal_handling": "异常处理",
    "cost_performance": "成本/性能",
}

JUDGE_DIMENSION_LABELS = {
    "reading_order_score": "阅读顺序 reading_order",
    "table_structure_score": "表格结构 table_structure",
    "evidence_alignment_score": "证据对齐 evidence_alignment",
}


def _safe_read_text(path: str | None, max_chars: int | None = None) -> str | None:
    if not path:
        return None
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


def render_score_metrics(case: dict) -> None:
    """总览指标卡：weighted_score / level / 契约 / backend / 页数 / 表格数 / metric 数。"""
    summary = case.get("summary") or {}
    score = case.get("score_result") or {}

    weighted = score.get("weighted_score", summary.get("weighted_score"))
    level = score.get("level", summary.get("level"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("加权总分 weighted_score", weighted if weighted is not None else "—")
    c2.metric("等级 level", level or "—")
    c3.metric("输出契约", "通过" if summary.get("output_contract_passed") else "未通过/缺失")
    c4.metric("backend", summary.get("backend") or "—")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("执行后端 execution_backend", summary.get("execution_backend") or "—")
    c6.metric("页数 page_count", summary.get("page_count") if summary.get("page_count") is not None else "—")
    c7.metric("表格数 raw_table_count", summary.get("raw_table_count") if summary.get("raw_table_count") is not None else "—")
    c8.metric("指标数 metric_record_count", summary.get("metric_record_count") if summary.get("metric_record_count") is not None else "—")


def render_dimension_chart(score_result: dict) -> None:
    """六维确定性分数条形图。"""
    dims = (score_result or {}).get("dimensions") or {}
    if not dims:
        st.info("暂无 score_result.json 的六维分数。请先运行 `python run.py --pipeline --cases ... --backend fixture`。")
        return
    rows = []
    for dim in SCORE_DIMENSIONS:
        val = dims.get(dim)
        if val is None:
            continue
        rows.append({"维度": DIMENSION_LABELS.get(dim, dim), "分数": float(val)})
    if not rows:
        st.info("六维分数均为空（financial_accuracy 等可能因无 GT 不可用）。")
        return
    df = pd.DataFrame(rows).set_index("维度")
    st.bar_chart(df, height=280)

    # 权重展示（如有）
    weights = (score_result or {}).get("weights_applied") or {}
    if weights:
        wrows = [{"维度": DIMENSION_LABELS.get(k, k), "权重": v} for k, v in weights.items()]
        with st.expander("查看各维度权重 weights_applied", expanded=False):
            st.dataframe(pd.DataFrame(wrows), use_container_width=True, hide_index=True)


def render_score_sources(score_result: dict) -> None:
    """明确区分 deterministic sources 与 llm_judge sources。"""
    sources = (score_result or {}).get("score_sources") or {}
    det = sources.get("deterministic") or []
    judge = sources.get("llm_judge") or []
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**确定性来源 deterministic**")
        if det:
            st.write("、".join(DIMENSION_LABELS.get(d, d) for d in det))
        else:
            st.caption("无")
    with c2:
        st.markdown("**LLM Judge 来源 llm_judge（不参与 weighted_score 重算）**")
        if judge:
            st.write("、".join(judge))
        else:
            st.caption("无（judge 未启用或无 judge_result）")


def render_judge_panel(judge_result: dict, judge_config: dict | None = None) -> None:
    """Judge 诊断面板：三维进度条 + deduction_items 表格 + enabled/mode。"""
    judge_config = judge_config or {}
    enabled = judge_config.get("enabled")
    cfg_mode = judge_config.get("mode")

    if not judge_result:
        st.info(
            "本 case 暂无 `judge_result.json`。"
            "若 `configs/judge.yaml` 中 `enabled=false` 则不会产生 Judge 结果；"
            "否则请先运行 `python run.py --pipeline --cases ... --backend fixture`。"
        )
        st.caption(f"judge.yaml: enabled={enabled} mode={cfg_mode}")
        return

    mode = judge_result.get("mode")
    c1, c2 = st.columns(2)
    c1.metric("Judge enabled", str(enabled))
    c2.metric("Judge mode", mode or cfg_mode or "—")

    st.markdown("##### 三维结构质量分（0–1）")
    for field, label in JUDGE_DIMENSION_LABELS.items():
        val = judge_result.get(field)
        cols = st.columns([3, 1])
        if isinstance(val, (int, float)):
            cols[0].progress(min(max(float(val), 0.0), 1.0), text=label)
            cols[1].metric(label.split(" ")[0], f"{float(val):.2f}")
        else:
            cols[0].progress(0.0, text=f"{label}（无分）")
            cols[1].metric(label.split(" ")[0], "—")

    confidence = judge_result.get("confidence")
    if confidence is not None:
        st.caption(f"Judge confidence: {confidence}")

    deductions = judge_result.get("deduction_items") or []
    st.markdown("##### 扣分项 deduction_items")
    if deductions:
        df = pd.DataFrame([
            {
                "维度 dimension": d.get("dimension"),
                "原因 reason": d.get("reason"),
                "证据 evidence": d.get("evidence"),
            }
            for d in deductions
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.success("无扣分项。")


def render_narrative(case: dict) -> None:
    """动态生成「组会讲述」叙事文案，全部来自真实 JSON 数据。"""
    summary = case.get("summary") or {}
    score = case.get("score_result") or {}
    judge = case.get("judge_result") or {}

    weighted = score.get("weighted_score", summary.get("weighted_score"))
    level = score.get("level", summary.get("level"))

    lines: list[str] = []
    if weighted is not None:
        lines.append(f"- 确定性加权总分 **{weighted}**（等级 **{level or '未知'}**）。")
    else:
        lines.append("- 暂无确定性加权总分（缺少 `score_result.json`）。")

    # 找出低于 0.8 的 Judge 维度
    low_dims = []
    for field, label in JUDGE_DIMENSION_LABELS.items():
        val = judge.get(field)
        if isinstance(val, (int, float)) and val < 0.8:
            low_dims.append((label, float(val)))

    deterministic_ok = isinstance(weighted, (int, float)) and weighted >= 8.0

    if judge and low_dims:
        detail = "、".join(f"{name}={val:.2f}" for name, val in low_dims)
        if deterministic_ok:
            lines.append(
                f"- 确定性评分整体可用，但 LLM Judge 在以下维度低于 0.8：{detail}，"
                "提示存在结构、阅读顺序或证据对齐问题，需要人工复核。"
            )
        else:
            lines.append(
                f"- 确定性评分偏低，且 Judge 在 {detail} 维度也低于 0.8，结构质量风险较高。"
            )
    elif judge:
        lines.append("- LLM Judge 三维结构质量分均不低于 0.8，未发现明显结构问题。")
    else:
        lines.append("- 未启用 LLM Judge 或无 Judge 结果，仅基于确定性信号判断。")

    # 准确率叙事
    num_acc = summary.get("numeric_accuracy")
    if summary.get("no_ground_truth"):
        lines.append("- 无可用人工 Ground Truth，本 case 不计入准确率评估，仅评测输出契约与结构。")
    elif num_acc is not None:
        lines.append(f"- 已对齐人工 GT，数值准确率 numeric_accuracy=**{num_acc}**。")

    ft = case.get("failure_trace") or {}
    targets = ft.get("suggested_targets") or []
    if targets:
        lines.append(f"- Failure trace 建议优化目标：{', '.join(targets)}。")

    st.markdown("\n".join(lines))
    st.caption("以上文案由当前 case 的真实 JSON 动态生成，未写死任何分数。")


def render_json_expander(title: str, data: Any, expanded: bool = False) -> None:
    """以 expander 形式展示 JSON 数据。"""
    with st.expander(title, expanded=expanded):
        if data in (None, {}, []):
            st.caption("（空）")
        else:
            st.json(data)


def render_markdown_preview(title: str, path: str | None, max_chars: int = 8000,
                            as_code: bool = False) -> None:
    """截断预览 Markdown / 文本产物，缺失时友好提示。"""
    st.markdown(f"**{title}**")
    if not path:
        render_missing_hint()
        return
    text = _safe_read_text(path, max_chars=max_chars)
    if text is None:
        render_missing_hint(path)
        return
    st.caption(f"来源：{path}")
    if as_code:
        st.code(text, language="markdown")
    else:
        st.markdown(text)


def render_json_file_preview(title: str, path: str | None, max_chars: int = 8000) -> None:
    """截断预览 JSON 产物文件（以 code 形式，避免超大 JSON 卡顿）。"""
    st.markdown(f"**{title}**")
    if not path:
        render_missing_hint()
        return
    text = _safe_read_text(path, max_chars=max_chars)
    if text is None:
        render_missing_hint(path)
        return
    st.caption(f"来源：{path}")
    st.code(text, language="json")


def render_missing_hint(path: str | None = None) -> None:
    """统一的缺文件友好提示。"""
    msg = "文件缺失，请先运行：`python run.py --pipeline --cases <yaml> --backend fixture`"
    if path:
        msg = f"未找到 `{path}`。\n\n" + msg
    st.warning(msg)


def render_missing_files(missing_files: list[str]) -> None:
    """渲染缺失文件清单。"""
    if not missing_files:
        st.success("无缺失产物。")
        return
    st.warning("以下产物缺失，部分面板可能无数据：")
    for m in missing_files:
        st.markdown(f"- `{m}`")
    st.caption("请运行：`python run.py --pipeline --cases <yaml> --backend fixture`")


def render_patch_list(patches: list[dict], title: str = "相关 Patch") -> None:
    """渲染 patch 列表：文件名、摘要、JSON 内容 expander。"""
    if not patches:
        st.caption("无相关 patch。")
        return
    st.markdown(f"**{title}（{len(patches)} 个）**")
    for p in patches:
        fname = p.get("_file") or p.get("patch_id") or "patch.json"
        reason = p.get("reason") or "（无摘要）"
        scope = p.get("target_scope") or "—"
        target = p.get("target_file") or "—"
        with st.expander(f"📄 {fname} — scope={scope}", expanded=False):
            st.markdown(f"- **target_file**: `{target}`")
            st.markdown(f"- **reason**: {reason}")
            improvement = p.get("expected_improvement")
            if improvement:
                st.markdown(f"- **expected_improvement**: {improvement}")
            risk = p.get("risk")
            if risk:
                st.markdown(f"- **risk**: {risk}")
            st.json(p)


def _trace_time(ts: str | None) -> str:
    if not ts:
        return ""
    if "T" in ts:
        return ts.split("T", 1)[1][:8]
    return ts[:8]


def _trace_detail(data: dict[str, Any]) -> str:
    errors = data.get("errors")
    if isinstance(errors, list) and errors:
        return f"errors={errors[0]}"
    keys = (
        "output_dir",
        "weighted_score",
        "level",
        "numeric_accuracy",
        "return_code",
        "passed",
        "failed",
        "reason",
        "skip_reason",
        "mode",
        "enabled",
        "artifact_count",
    )
    parts = []
    for key in keys:
        value = data.get(key)
        if value not in (None, "", []):
            parts.append(f"{key}={value}")
    return "; ".join(parts)


def run_trace_event_rows(events: list[dict]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        rows.append({
            "time": _trace_time(event.get("ts")),
            "stage": event.get("stage") or "",
            "kind": event.get("kind") or "",
            "status": event.get("status") or "",
            "duration_ms": event.get("duration_ms"),
            "detail": _trace_detail(data),
        })
    return rows


def render_run_trace(run_trace: dict) -> None:
    events = run_trace.get("events") or []
    summary = run_trace.get("summary") or {}
    if not run_trace.get("exists") or not events:
        st.info("No offline run trace is available for this case yet.")
        path = run_trace.get("path")
        if path:
            st.caption(f"Expected path: {path}")
        return

    st.caption(f"Trace file: {run_trace.get('path')}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Events", summary.get("event_count", 0))
    c2.metric("Stages", summary.get("stage_count", 0))
    c3.metric("Failed stages", summary.get("failed_count", 0))
    c4.metric("Total ms", summary.get("total_duration_ms", 0))

    stages = summary.get("stages") or []
    if stages:
        st.markdown("##### Stage Timeline")
        st.dataframe(pd.DataFrame(stages), use_container_width=True, hide_index=True)

    rows = run_trace_event_rows(events)
    st.markdown("##### Event Stream")
    status_options = sorted({row["status"] for row in rows if row["status"]})
    selected_status = st.multiselect("status", status_options, default=status_options)
    filtered = [
        row for row in rows
        if not selected_status or not row["status"] or row["status"] in selected_status
    ]
    st.dataframe(pd.DataFrame(filtered), use_container_width=True, hide_index=True)

    with st.expander("Raw trace events.jsonl", expanded=False):
        st.json(events)
