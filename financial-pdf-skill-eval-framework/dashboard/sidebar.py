"""Streamlit 侧边栏：全局配置、状态摘要、操作入口。

参考 Auto_prd_test_agent 的 ui/sidebar.py 组织方式，但业务内容换成
只读评测 Dashboard：case 选择、bundle 生成时间、输出目录、缺失文件摘要、
Judge 配置摘要，以及「刷新 bundle」按钮（仅重新扫描本地文件，绝不跑真实 LAS/OpenClaw）。
"""
from __future__ import annotations

from typing import Any

import streamlit as st

DEFAULT_CASE_ID = "byd_real_las_fixture"


def _case_label(case: dict) -> str:
    cid = case.get("case_id") or "(unknown)"
    name = case.get("name")
    return f"{cid}" if not name or name == cid else f"{cid} · {name}"


def render_sidebar(bundle: dict) -> dict | None:
    """渲染侧边栏，返回当前选中的 case dict（无 case 时返回 None）。"""
    cases: list[dict] = bundle.get("cases") or []

    with st.sidebar:
        st.header("⚙️ 评测 Dashboard 配置")

        # 1. 刷新 bundle（仅重新扫描本地文件）
        if st.button("🔄 刷新 bundle（仅读盘）", use_container_width=True):
            _refresh_bundle()

        st.divider()

        # 2. case 选择器
        st.subheader("📂 选择 Case")
        if not cases:
            st.warning("bundle 中没有任何 case。请先运行 pipeline 生成产物。")
            return None

        case_ids = [c.get("case_id") for c in cases]
        default_index = 0
        default_pref = bundle.get("default_case_id", DEFAULT_CASE_ID)
        if default_pref in case_ids:
            default_index = case_ids.index(default_pref)

        selected_id = st.selectbox(
            "case_id",
            options=case_ids,
            index=default_index,
            format_func=lambda cid: next(
                (_case_label(c) for c in cases if c.get("case_id") == cid), cid
            ),
        )
        selected_case = next((c for c in cases if c.get("case_id") == selected_id), cases[0])

        st.divider()

        # 3. 状态摘要
        st.subheader("📊 状态摘要")
        st.caption(f"bundle 生成时间：{bundle.get('generated_at', '—')}")
        st.caption(f"framework_root：{bundle.get('framework_root', '—')}")
        st.markdown(f"**当前 case 输出目录：**")
        st.code(selected_case.get("output_dir") or "（未配置）", language="text")

        # 4. 缺失文件摘要
        missing = selected_case.get("missing_files") or []
        if missing:
            st.error(f"⚠️ 缺失 {len(missing)} 个产物")
            with st.expander("查看缺失清单", expanded=False):
                for m in missing:
                    st.markdown(f"- `{m}`")
        else:
            st.success("✅ 产物齐全")

        st.divider()

        # 5. Judge 配置摘要
        st.subheader("🤖 Judge 配置")
        jc: dict[str, Any] = bundle.get("judge_config") or {}
        st.caption(f"enabled：{jc.get('enabled')}")
        st.caption(f"mode：{jc.get('mode')}")
        st.caption(f"judge_version：{jc.get('judge_version')}")
        st.caption(f"配置文件：{bundle.get('judge_config_path')}")

    return selected_case


def _refresh_bundle() -> None:
    """仅重新扫描本地文件并重建 bundle，绝不触发真实 LAS / OpenClaw。"""
    try:
        from framework.dashboard_bundle import build_dashboard_bundle

        bundle = build_dashboard_bundle()
        st.session_state["_dashboard_bundle"] = bundle
        st.success(f"已刷新 bundle（{len(bundle.get('cases') or [])} 个 case，纯本地读盘）。")
        st.rerun()
    except Exception as e:  # noqa: BLE001
        st.error(f"刷新失败：{e}")
