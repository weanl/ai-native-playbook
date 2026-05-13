"""Streamlit UI for NextAIOpsAlgoApp — data upload, algorithm run, batch experiment, visualization."""

import json
import tempfile
from pathlib import Path
from typing import cast

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from nextaiops_algo.algorithms.params import AlgorithmParamSpec, format_experiment_label
from nextaiops_algo.algorithms.registry import get_algorithm_param_specs, list_algorithms
from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.table import FieldRole, Table
from nextaiops_algo.datasets.registry import get_builtin, list_builtin
from nextaiops_algo.pipeline.preprocess import read_csv_to_table, read_to_table
from nextaiops_algo.pipeline.profile import TableProfile, profile_table
from nextaiops_algo.pipeline.run import run_experiment
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore
from nextaiops_algo.viz.preview import render_data_preview

st.set_page_config(page_title="NextAIOpsAlgoApp", layout="wide")

st.title("NextAIOpsAlgoApp — 智能运维算法平台")


# ── Helper functions (defined before use) ────────────────────


def _get_input_table() -> tuple[bool, Table | None, str]:
    """Common data source selector shared by single and batch pages.

    Returns (upload_ok, table, source_description).
    """
    data_source = st.sidebar.selectbox(
        "数据来源",
        ["上传 CSV", "上传 .out", "上传 npy/npz"] + list_builtin(),
    )

    if data_source == "上传 CSV":
        uploaded_file = st.file_uploader("上传指标数据 CSV", type=["csv"], key="csv_upload")
        if uploaded_file is None:
            return False, None, ""
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
            return True, table, str(csv_path)
        except SchemaValidationError as e:
            st.error(f"数据格式校验失败：{e}")
            return False, None, ""

    elif data_source == "上传 .out":
        uploaded_file = st.file_uploader("上传 TSB-UAD .out 文件", type=["out"], key="out_upload")
        if uploaded_file is None:
            return False, None, ""
        with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tmp:
            tmp.write(uploaded_file.getvalue())
            out_path = Path(tmp.name)
        try:
            table = read_to_table(out_path)
            return True, table, str(out_path)
        except SchemaValidationError as e:
            st.error(f"数据格式校验失败：{e}")
            return False, None, ""

    elif data_source == "上传 npy/npz":
        uploaded_file = st.file_uploader("上传 npy/npz 文件", type=["npy", "npz"], key="npy_upload")
        if uploaded_file is None:
            return False, None, ""
        suffix = Path(uploaded_file.name).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(uploaded_file.getvalue())
            array_path = Path(tmp.name)
        try:
            table = read_to_table(array_path)
            return True, table, str(array_path)
        except SchemaValidationError as e:
            st.error(f"数据格式校验失败：{e}")
            return False, None, ""

    else:
        try:
            table = get_builtin(data_source).load()
            return True, table, data_source
        except Exception as e:
            st.error(f"加载内置数据集失败：{e}")
            return False, None, ""


def _render_param_form(algorithm_name: str) -> dict[str, object] | None:
    """Render algorithm parameter controls and return params."""
    specs = get_algorithm_param_specs(algorithm_name)
    if not specs:
        with st.expander("算法参数（JSON）"):
            params_str = st.text_area("参数", value="{}", key=f"params_json_{algorithm_name}")
        try:
            parsed_params = json.loads(params_str)
        except json.JSONDecodeError as e:
            st.error(f"参数 JSON 格式错误：{e}")
            return None
        if not isinstance(parsed_params, dict):
            st.error("参数 JSON 必须是对象")
            return None
        return cast(dict[str, object], parsed_params)

    st.subheader("算法参数")
    params: dict[str, object] = {}
    for spec in specs:
        params[spec.name] = _render_param_control(algorithm_name, spec)

    identity_params = {
        spec.name: params[spec.name]
        for spec in specs
        if spec.affects_run_identity and spec.name in params
    }
    st.caption(f"实验标识：{format_experiment_label(algorithm_name, identity_params)}")
    return params


def _render_param_control(algorithm_name: str, spec: AlgorithmParamSpec) -> object:
    """Render a single parameter control from metadata."""
    key = f"param_{algorithm_name}_{spec.name}"
    label = f"{spec.name}（默认 {spec.default}）"

    if spec.type == "float":
        default = _default_float(spec.default)
        return float(
            st.number_input(
                label,
                value=default,
                min_value=spec.min_value,
                max_value=spec.max_value,
                help=spec.description,
                key=key,
            )
        )
    if spec.type == "int":
        min_value = int(spec.min_value) if spec.min_value is not None else None
        max_value = int(spec.max_value) if spec.max_value is not None else None
        default = _default_int(spec.default)
        return int(
            st.number_input(
                label,
                value=default,
                min_value=min_value,
                max_value=max_value,
                step=1,
                help=spec.description,
                key=key,
            )
        )
    if spec.type == "bool":
        return bool(st.checkbox(label, value=bool(spec.default), help=spec.description, key=key))
    if spec.type == "enum" and spec.choices:
        default_index = spec.choices.index(spec.default) if spec.default in spec.choices else 0
        return st.selectbox(
            label,
            options=list(spec.choices),
            index=default_index,
            help=spec.description,
            key=key,
        )
    return st.text_input(label, value=str(spec.default), help=spec.description, key=key)


def _default_float(value: object) -> float:
    """Convert metadata default to float for Streamlit controls."""
    if isinstance(value, bool):
        raise ValueError("Boolean default cannot be used as float")
    if isinstance(value, (str, int, float)):
        return float(value)
    raise ValueError(f"Unsupported float default: {value!r}")


def _default_int(value: object) -> int:
    """Convert metadata default to int for Streamlit controls."""
    if isinstance(value, bool):
        raise ValueError("Boolean default cannot be used as int")
    if isinstance(value, (str, int, float)):
        return int(value)
    raise ValueError(f"Unsupported int default: {value!r}")


def _render_data_preview(table: Table) -> None:
    """Render schema, quality, and curve preview for a table."""
    profile = profile_table(table)

    st.subheader("数据预览")
    _render_profile_summary(profile)

    mapping_df = pd.DataFrame(
        [
            {
                "列名": column.name,
                "角色": column.role.value,
                "dtype": column.dtype,
                "缺失数": column.missing_count,
                "缺失率": f"{column.missing_rate:.2%}",
                "唯一值": column.unique_count,
            }
            for column in profile.columns
        ]
    )
    st.dataframe(mapping_df, use_container_width=True, hide_index=True)

    metric_options = list(profile.metric_columns)
    selected_metric = st.selectbox(
        "预览指标",
        options=metric_options,
        key="preview_metric",
    )
    preview_fig = render_data_preview(table, metric_name=selected_metric)
    st.plotly_chart(preview_fig, use_container_width=True)

    with st.expander("原始数据样例"):
        st.dataframe(table.df.head(20), use_container_width=True)


def _render_profile_summary(profile: TableProfile) -> None:
    """Render compact data profile metrics."""
    summary_cols = st.columns(4)
    summary_cols[0].metric("行数", profile.row_count)
    summary_cols[1].metric("列数", profile.column_count)
    summary_cols[2].metric("指标列", len(profile.metric_columns))
    summary_cols[3].metric("标签列", profile.label_column or "无")

    if profile.label is None:
        st.info("当前数据没有真实异常标签，运行后无法计算监督评估指标。")
        return

    label_cols = st.columns(4)
    label_cols[0].metric("真实异常点", profile.label.true_anomalies)
    label_cols[1].metric("异常比例", f"{profile.label.anomaly_rate:.2%}")
    label_cols[2].metric("异常段数", profile.label.segment_count)
    label_cols[3].metric("最长异常段", profile.label.longest_segment)


def _render_single_experiment(upload_ok: bool, input_table: Table | None, data_source: str) -> None:
    """Render single algorithm experiment page."""
    if not upload_ok:
        st.info("请先在侧边栏选择或上传数据")
        return

    st.header("单算法实验")

    algo_names = list_algorithms()
    if not algo_names:
        st.warning("无可用算法")
        return

    selected_algo = st.selectbox("选择算法", algo_names)
    params = _render_param_form(selected_algo)
    if params is None:
        return

    if st.button("跑实验", type="primary"):
        with st.spinner("实验运行中..."):
            try:
                result = run_experiment(
                    dataset_path=data_source,
                    algorithm_name=selected_algo,
                    params=params,
                )
                st.session_state["last_result"] = result
                st.success(f"实验完成! run_id={result.run_id}")
            except SchemaValidationError as e:
                st.error(f"Schema 校验失败：{e}")

    if "last_result" in st.session_state:
        result = st.session_state["last_result"]
        st.subheader(f"最近实验 (run_id: {result.run_id})")

        metrics_df = pd.DataFrame(
            [{"指标": k, "值": round(v, 4)} for k, v in result.metrics.items()]
        )
        st.dataframe(metrics_df, use_container_width=True, hide_index=True)

        viz_path = Path(result.artifacts_path) / "viz.html"
        if viz_path.exists():
            components.html(viz_path.read_text(), height=600, scrolling=True)
        else:
            st.warning("viz.html 未生成")


def _render_batch_experiment(upload_ok: bool, input_table: Table | None, data_source: str) -> None:
    """Render batch experiment page with leaderboard, overlay, heatmap tabs."""
    if not upload_ok:
        st.info("请先在侧边栏选择或上传数据")
        return

    st.header("批量实验")

    from nextaiops_algo.algorithms.registry import REGISTRY
    from nextaiops_algo.pipeline.batch import run_batch
    from nextaiops_algo.viz.heatmap import render_heatmap
    from nextaiops_algo.viz.leaderboard import render_leaderboard
    from nextaiops_algo.viz.overlay import render_overlay

    algo_names = sorted(REGISTRY.keys())
    if not algo_names:
        st.warning("无可用算法")
        return

    st.subheader("选择算法")
    select_all = st.checkbox("全选", value=True)

    selected_algos: list[str] = []
    for algo in algo_names:
        if st.checkbox(algo, value=select_all, key=f"batch_algo_{algo}"):
            selected_algos.append(algo)

    if not selected_algos:
        st.warning("请至少选择一个算法")
        return

    tsbuad_algos = ["iforest", "lof", "ocsvm", "pca", "hbos"]
    has_tsbuad = any(a in algo_names for a in tsbuad_algos)
    if not has_tsbuad:
        st.info("安装 `nextaiops-algo[tsbuad]` 可解锁更多算法 (IForest, LOF, OCSVM, PCA, HBOS)")

    if st.button("开始批量实验", type="primary"):
        with st.spinner(f"批量运行 {len(selected_algos)} 个算法..."):
            try:
                batch = run_batch(
                    dataset=data_source,
                    algorithms=selected_algos,
                )
                st.session_state["last_batch"] = batch
                st.session_state["batch_input_table"] = input_table
                st.success(f"批量实验完成! batch_id={batch.batch_id}, 状态={batch.status.value}")
            except Exception as e:
                st.error(f"批量实验失败：{e}")

    if "last_batch" in st.session_state:
        batch = st.session_state["last_batch"]
        batch_input = st.session_state.get("batch_input_table")

        tab1, tab2, tab3 = st.tabs(["排行榜", "时序叠加对比", "热力图"])

        with tab1:
            store = SqliteTrackingStore()
            lb_df = render_leaderboard(batch, store=store)
            st.dataframe(lb_df, use_container_width=True, hide_index=True)

        with tab2:
            if batch_input is not None:
                fig = render_overlay(batch, batch_input)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("原始数据不可用，无法渲染时序叠加")

        with tab3:
            store = SqliteTrackingStore()
            hm_fig = render_heatmap(batch, store=store)
            st.plotly_chart(hm_fig, use_container_width=True)

    st.subheader("查看历史批量实验")
    store = SqliteTrackingStore()
    batches = store.list_batches(limit=20)

    if batches:
        batch_options = {
            b.batch_id: f"{b.batch_id} — {b.dataset_source} ({b.status.value})" for b in batches
        }
        selected_batch_id = st.selectbox(
            "选择历史批量实验",
            options=list(batch_options.keys()),
            format_func=lambda bid: batch_options[bid],
        )
        selected_batch = next(b for b in batches if b.batch_id == selected_batch_id)

        tab1, tab2, tab3 = st.tabs(["排行榜", "时序叠加对比", "热力图"])

        with tab1:
            lb_df = render_leaderboard(selected_batch, store=store)
            st.dataframe(lb_df, use_container_width=True, hide_index=True)

        with tab3:
            hm_fig = render_heatmap(selected_batch, store=store)
            st.plotly_chart(hm_fig, use_container_width=True)
    else:
        st.info("暂无历史批量实验记录")


def _render_history() -> None:
    """Render history page for single experiment runs."""
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
                    "PA-F1": round(metrics.get("pa_f1", 0.0), 4),
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


# ── Sidebar: page selection ─────────────────────────────────
page = st.sidebar.radio("功能页面", ["单算法实验", "批量实验", "历史记录"])

# ── Shared: data source ─────────────────────────────────────
upload_ok, input_table, data_source_desc = _get_input_table()

if upload_ok and input_table is not None:
    metric_cols = input_table.schema.columns_of(FieldRole.METRIC)
    if len(metric_cols) > 1:
        st.info(f"检测到 {len(metric_cols)} 个 METRIC 列：{', '.join(metric_cols)}")

    _render_data_preview(input_table)

# ── Page routing ────────────────────────────────────────────
if page == "单算法实验":
    _render_single_experiment(upload_ok, input_table, data_source_desc)
elif page == "批量实验":
    _render_batch_experiment(upload_ok, input_table, data_source_desc)
elif page == "历史记录":
    _render_history()
