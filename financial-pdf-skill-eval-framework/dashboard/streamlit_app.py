"""金融 PDF Skill 评测 Dashboard —— Streamlit 主控台（只读）。

参考 Auto_prd_test_agent 的 ui/main.py 三层结构（main / sidebar / components），
但业务内容换成只读评测 Dashboard：仅读取 reports/dashboard/dashboard_bundle.json
及其引用的本地 JSON / Markdown 产物，不触发任何评估、推理或 Skill 调用。

启动：
    streamlit run dashboard/streamlit_app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

# 确保 framework 根目录在 sys.path 上（脚本方式运行 streamlit 时需要）。
FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
if str(FRAMEWORK_ROOT) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_ROOT))

from dashboard import components as C  # noqa: E402
from dashboard.sidebar import render_sidebar  # noqa: E402

BUNDLE_PATH = FRAMEWORK_ROOT / "reports" / "dashboard" / "dashboard_bundle.json"


def _load_bundle() -> dict | None:
    """加载 bundle：优先用 session 中刷新过的版本，否则读磁盘 JSON。"""
    if "_dashboard_bundle" in st.session_state:
        return st.session_state["_dashboard_bundle"]
    if not BUNDLE_PATH.exists():
        return None
    try:
        bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        st.error(f"读取 bundle 失败：{e}")
        return None
    st.session_state["_dashboard_bundle"] = bundle
    return bundle


def _render_overview(case: dict, bundle: dict) -> None:
    st.subheader("总览")
    C.render_score_metrics(case)
    st.divider()

    left, right = st.columns([0.55, 0.45], gap="large")
    with left:
        st.markdown("##### 六维确定性分数")
        C.render_dimension_chart(case.get("score_result") or {})
    with right:
        st.markdown("##### 评分来源")
        C.render_score_sources(case.get("score_result") or {})
        st.markdown("##### 运行元信息 run_meta")
        meta = case.get("summary") or {}
        st.write({
            "output_contract_passed": meta.get("output_contract_passed"),
            "backend": meta.get("backend"),
            "execution_backend": meta.get("execution_backend"),
            "page_count": meta.get("page_count"),
            "raw_table_count": meta.get("raw_table_count"),
            "financial_table_count": meta.get("financial_table_count"),
            "metric_record_count": meta.get("metric_record_count"),
        })


def _render_run_trace(case: dict, bundle: dict) -> None:
    st.subheader("Run Trace")
    C.render_run_trace(case.get("run_trace") or {})


def _render_judge(case: dict, bundle: dict) -> None:
    st.subheader("Judge 诊断")
    left, right = st.columns([0.55, 0.45], gap="large")
    with left:
        C.render_judge_panel(case.get("judge_result") or {}, bundle.get("judge_config") or {})
    with right:
        C.render_json_expander("judge_result.json 原始内容", case.get("judge_result"), expanded=False)
        st.caption("LLM-as-a-Judge 仅作结构质量诊断，不参与 weighted_score 重算。")


def _render_narrative(case: dict, bundle: dict) -> None:
    st.subheader("叙事对比")
    left, right = st.columns([0.5, 0.5], gap="large")
    with left:
        st.markdown("##### 组会讲述文案（动态生成）")
        C.render_narrative(case)
    with right:
        st.markdown("##### 关键指标对照")
        summary = case.get("summary") or {}
        score = case.get("score_result") or {}
        st.write({
            "weighted_score": score.get("weighted_score", summary.get("weighted_score")),
            "level": score.get("level", summary.get("level")),
            "numeric_accuracy": summary.get("numeric_accuracy"),
            "no_ground_truth": summary.get("no_ground_truth"),
            "judge_reading_order": (case.get("judge_result") or {}).get("reading_order_score"),
            "judge_table_structure": (case.get("judge_result") or {}).get("table_structure_score"),
            "judge_evidence_alignment": (case.get("judge_result") or {}).get("evidence_alignment_score"),
        })


def _render_skillopt(case: dict, bundle: dict) -> None:
    st.subheader("Failure Trace & SkillOpt")
    ft = case.get("failure_trace") or {}
    left, right = st.columns([0.5, 0.5], gap="large")
    with left:
        st.markdown("##### 建议优化目标 suggested_targets")
        targets = ft.get("suggested_targets") or []
        if targets:
            for t in targets:
                st.markdown(f"- `{t}`")
        else:
            st.caption("无 suggested_targets。")
        C.render_json_expander("failure_trace.json 原始内容", ft, expanded=bool(ft))
    with right:
        st.markdown("##### 相关 proposed patches")
        C.render_patch_list(case.get("patches") or [], title="本 case 关联 Patch")
        gp = bundle.get("global_patches") or []
        if gp:
            st.markdown("##### 全局 / 未归属 patches")
            C.render_patch_list(gp, title="全局 Patch")


def _render_artifacts(case: dict, bundle: dict) -> None:
    st.subheader("解析产物")
    artifacts = case.get("artifacts") or {}
    left, right = st.columns([0.5, 0.5], gap="large")
    with left:
        C.render_markdown_preview(
            "raw/parsed.md 预览（截断）",
            artifacts.get("parsed_md_path"),
            max_chars=8000,
            as_code=True,
        )
    with right:
        C.render_json_file_preview(
            "normalized/normalized_tables.json 预览（截断）",
            artifacts.get("normalized_tables_path"),
            max_chars=8000,
        )
    st.divider()
    C.render_missing_files(case.get("missing_files") or [])


def _render_rubric(case: dict, bundle: dict) -> None:
    st.subheader("评分标准 Rubric")
    rubric_rel = bundle.get("rubric_path") or "judge/assessment_skill.md"
    rubric_abs = FRAMEWORK_ROOT / rubric_rel
    C.render_markdown_preview(
        f"{rubric_rel}（可追溯评分标准）",
        str(rubric_abs),
        max_chars=20000,
        as_code=False,
    )


def main() -> None:
    st.set_page_config(page_title="金融 PDF Skill 评测 Dashboard", layout="wide")
    st.title("📑 金融 PDF Skill 评测 Dashboard")
    st.caption("只读展示已落盘的评测产物（JSON / Markdown）。不触发任何真实 LAS / OpenClaw 调用。")

    bundle = _load_bundle()
    if bundle is None:
        st.error("未找到 `reports/dashboard/dashboard_bundle.json`。")
        st.markdown("请先生成数据包：")
        st.code("python run.py --build-dashboard-bundle", language="powershell")
        st.info("若页面提示缺数据，请先运行 pipeline："
                "`python run.py --pipeline --cases testcases/pdf_cases/byd_real_las_fixture.yaml --backend fixture`")
        return

    selected_case = render_sidebar(bundle)
    if selected_case is None:
        st.warning("当前没有可展示的 case。请先运行 pipeline 生成产物，再刷新 bundle。")
        return

    tab_overview, tab_run_trace, tab_judge, tab_narrative, tab_skillopt, tab_artifacts, tab_rubric = st.tabs(
        ["总览", "Run Trace", "Judge 诊断", "叙事对比", "Failure Trace & SkillOpt", "解析产物", "Rubric"]
    )
    with tab_overview:
        _render_overview(selected_case, bundle)
    with tab_run_trace:
        _render_run_trace(selected_case, bundle)
    with tab_judge:
        _render_judge(selected_case, bundle)
    with tab_narrative:
        _render_narrative(selected_case, bundle)
    with tab_skillopt:
        _render_skillopt(selected_case, bundle)
    with tab_artifacts:
        _render_artifacts(selected_case, bundle)
    with tab_rubric:
        _render_rubric(selected_case, bundle)


if __name__ == "__main__":
    main()
else:
    # `streamlit run` 与 `import dashboard.streamlit_app` 都会执行模块体；
    # 仅在被 streamlit 执行时渲染（通过 st.runtime 判断），import 检查时不渲染。
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        if get_script_run_ctx() is not None:
            main()
    except Exception:
        pass
