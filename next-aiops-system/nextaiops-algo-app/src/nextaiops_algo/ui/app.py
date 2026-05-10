"""Streamlit UI for NextAIOpsAlgoApp — data upload, algorithm run, visualization."""

import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from nextaiops_algo.algorithms.registry import list_algorithms
from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.table import FieldRole
from nextaiops_algo.pipeline.preprocess import read_csv_to_table
from nextaiops_algo.pipeline.run import run_experiment
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore

st.set_page_config(page_title="NextAIOpsAlgoApp", layout="wide")

st.title("NextAIOpsAlgoApp — 智能运维算法平台")

# ── 1. 上传数据 ──────────────────────────────────────────
st.header("1. 上传数据")
uploaded_file = st.file_uploader("上传指标数据 CSV", type=["csv"])

upload_ok = False
if uploaded_file is not None:
    if (
        "csv_path" not in st.session_state
        or st.session_state.get("uploaded_name") != uploaded_file.name
    ):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(uploaded_file.getvalue())
            csv_tmp_path = Path(tmp.name)
        st.session_state["csv_path"] = csv_tmp_path
        st.session_state["uploaded_name"] = uploaded_file.name

    csv_path: Path = st.session_state["csv_path"]

    try:
        table = read_csv_to_table(csv_path)
        upload_ok = True
    except SchemaValidationError as e:
        st.error(f"数据格式校验失败：{e}")

    if upload_ok:
        # Field inference mapping display
        st.subheader("字段推断结果（列名 → 角色）")
        mapping_df = pd.DataFrame(
            [{"列名": col, "角色": role.value} for col, role in table.schema.roles.items()]
        )
        st.dataframe(mapping_df, use_container_width=True, hide_index=True)

        metric_cols = table.schema.columns_of(FieldRole.METRIC)
        if len(metric_cols) > 1:
            st.info(f"检测到 {len(metric_cols)} 个 METRIC 列：{', '.join(metric_cols)}")
        st.caption("如映射不正确，M1 将支持手动覆盖")

        with st.expander("数据预览"):
            st.dataframe(table.df.head(10), use_container_width=True)

# ── 2. 选算法 + 跑实验 ──────────────────────────────────
if upload_ok:
    st.header("2. 选算法 + 跑实验")

    algo_names = list_algorithms()
    if not algo_names:
        st.warning("无可用算法")
    else:
        selected_algo = st.selectbox("选择算法", algo_names)

        with st.expander("算法参数（JSON）"):
            params_str = st.text_area("参数", value="{}")

        if st.button("跑实验", type="primary"):
            try:
                params = json.loads(params_str)
            except json.JSONDecodeError as e:
                st.error(f"参数 JSON 格式错误：{e}")
            else:
                with st.spinner("实验运行中..."):
                    try:
                        result = run_experiment(
                            dataset_path=st.session_state["csv_path"],
                            algorithm_name=selected_algo,
                            params=params,
                        )
                        st.session_state["last_result"] = result
                        st.success(f"实验完成! run_id={result.run_id}")
                    except SchemaValidationError as e:
                        st.error(f"Schema 校验失败：{e}")

# ── 3. 看图 ──────────────────────────────────────────────
if "last_result" in st.session_state:
    st.header("3. 看图")

    result = st.session_state["last_result"]
    st.subheader(f"最近实验 (run_id: {result.run_id})")

    metrics_df = pd.DataFrame([{"指标": k, "值": round(v, 4)} for k, v in result.metrics.items()])
    st.dataframe(metrics_df, use_container_width=True, hide_index=True)

    viz_path = Path(result.artifacts_path) / "viz.html"
    if viz_path.exists():
        components.html(viz_path.read_text(), height=600, scrolling=True)
    else:
        st.warning("viz.html 未生成")

# ── 历史实验记录 ──────────────────────────────────────────
st.header("历史实验记录")

store = SqliteTrackingStore()
runs = store.list_runs(limit=20)

if runs:
    history_data = []
    for run in runs:
        metrics = store.get_metrics(run.run_id)
        history_data.append(
            {
                "run_id": run.run_id,
                "算法": run.algorithm_name,
                "数据集": run.dataset_version,
                "F1": round(metrics.get("f1", 0.0), 4),
                "Precision": round(metrics.get("precision", 0.0), 4),
                "Recall": round(metrics.get("recall", 0.0), 4),
                "时间": run.created_at.strftime("%Y-%m-%d %H:%M"),
            }
        )
    st.dataframe(pd.DataFrame(history_data), use_container_width=True, hide_index=True)

    run_label_map = {r.run_id: f"{r.run_id} — {r.algorithm_name}" for r in runs}
    selected_run_id = st.selectbox(
        "查看历史实验可视化",
        options=list(run_label_map.keys()),
        format_func=lambda rid: run_label_map[rid],
    )
    selected_run = next(r for r in runs if r.run_id == selected_run_id)
    viz_path = Path(selected_run.artifacts_path) / "viz.html"
    if viz_path.exists():
        components.html(viz_path.read_text(), height=600, scrolling=True)
else:
    st.info("暂无历史实验记录")
