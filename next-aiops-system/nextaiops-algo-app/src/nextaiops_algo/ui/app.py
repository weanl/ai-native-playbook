"""Streamlit UI for NextAIOpsAlgoApp — data upload, algorithm run, batch experiment, visualization."""

import json
import tempfile
from pathlib import Path
from typing import Any, cast

import pandas as pd
import streamlit as st

from nextaiops_algo.algorithms.params import AlgorithmParamSpec, format_experiment_label
from nextaiops_algo.algorithms.registry import get_algorithm_param_specs, list_algorithms
from nextaiops_algo.core.exceptions import SchemaValidationError
from nextaiops_algo.core.experiment import RunStatus
from nextaiops_algo.core.table import FieldRole, Table
from nextaiops_algo.datasets.registry import get_builtin, list_builtin
from nextaiops_algo.pipeline.batch_bundle import BatchBundleResult
from nextaiops_algo.pipeline.dataset_bundle import DatasetBundle
from nextaiops_algo.pipeline.preprocess import (
    read_csv_to_table,
    read_dataset_bundle,
    read_dataset_bundle_from_zip,
    read_to_table,
)
from nextaiops_algo.pipeline.profile import TableProfile, profile_table
from nextaiops_algo.pipeline.run import run_experiment
from nextaiops_algo.pipeline.run_bundle import BundleRunResult, run_bundle_experiment
from nextaiops_algo.storage.sqlite_tracking import SqliteTrackingStore
from nextaiops_algo.viz.preview import render_data_preview

st.set_page_config(page_title="NextAIOpsAlgoApp", layout="wide")

st.title("NextAIOpsAlgoApp — 智能运维算法平台")


# ── Helper functions (defined before use) ────────────────────


def _get_input_table() -> tuple[bool, Table | None, str, DatasetBundle | None]:
    """Common data source selector shared by single and batch pages.

    Returns (upload_ok, table, source_description, optional_bundle).
    """
    data_source = st.sidebar.selectbox(
        "数据来源",
        ["上传 CSV", "上传 .out", "上传 npy/npz", "上传 zip"] + list_builtin(),
    )

    if data_source == "上传 CSV":
        uploaded_files = st.file_uploader(
            "上传指标数据 CSV",
            type=["csv"],
            accept_multiple_files=True,
            key="csv_upload",
        )
        if not uploaded_files:
            return False, None, "", None
        upload_paths = _save_uploaded_files(cast(list[Any], uploaded_files), "csv_upload_paths")
        try:
            if len(upload_paths) == 1:
                table = read_csv_to_table(upload_paths[0])
                return True, table, str(upload_paths[0]), None
            bundle = read_dataset_bundle(upload_paths, dataset_id=_bundle_dataset_id(upload_paths))
            return True, bundle.files[0].table, bundle.dataset_id, bundle
        except SchemaValidationError as e:
            st.error(f"数据格式校验失败：{e}")
            return False, None, "", None

    elif data_source == "上传 .out":
        uploaded_files = st.file_uploader(
            "上传 TSB-UAD .out 文件",
            type=["out"],
            accept_multiple_files=True,
            key="out_upload",
        )
        if not uploaded_files:
            return False, None, "", None
        upload_paths = _save_uploaded_files(cast(list[Any], uploaded_files), "out_upload_paths")
        try:
            if len(upload_paths) == 1:
                table = read_to_table(upload_paths[0])
                return True, table, str(upload_paths[0]), None
            bundle = read_dataset_bundle(upload_paths, dataset_id=_bundle_dataset_id(upload_paths))
            return True, bundle.files[0].table, bundle.dataset_id, bundle
        except SchemaValidationError as e:
            st.error(f"数据格式校验失败：{e}")
            return False, None, "", None

    elif data_source == "上传 npy/npz":
        uploaded_files = st.file_uploader(
            "上传 npy/npz 文件",
            type=["npy", "npz"],
            accept_multiple_files=True,
            key="npy_upload",
        )
        if not uploaded_files:
            return False, None, "", None
        upload_paths = _save_uploaded_files(cast(list[Any], uploaded_files), "npy_upload_paths")
        try:
            if len(upload_paths) == 1:
                table = read_to_table(upload_paths[0])
                return True, table, str(upload_paths[0]), None
            bundle = read_dataset_bundle(upload_paths, dataset_id=_bundle_dataset_id(upload_paths))
            return True, bundle.files[0].table, bundle.dataset_id, bundle
        except SchemaValidationError as e:
            st.error(f"数据格式校验失败：{e}")
            return False, None, "", None

    elif data_source == "上传 zip":
        uploaded_file = st.file_uploader("上传数据集 zip", type=["zip"], key="zip_upload")
        if uploaded_file is None:
            return False, None, "", None
        zip_path = _save_uploaded_file(cast(Any, uploaded_file), "zip_upload_path")
        extract_dir = Path(tempfile.mkdtemp(prefix="nextaiops_zip_"))
        try:
            bundle = read_dataset_bundle_from_zip(
                zip_path,
                extract_dir=extract_dir,
                dataset_id=Path(uploaded_file.name).stem,
            )
            return True, bundle.files[0].table, bundle.dataset_id, bundle
        except SchemaValidationError as e:
            st.error(f"数据格式校验失败：{e}")
            return False, None, "", None

    else:
        try:
            table = get_builtin(data_source).load()
            return True, table, data_source, None
        except Exception as e:
            st.error(f"加载内置数据集失败：{e}")
            return False, None, "", None


def _save_uploaded_files(uploaded_files: list[Any], state_key: str) -> list[Path]:
    """Persist uploaded files under a stable temp directory for experiment runs."""
    names = tuple(str(uploaded_file.name) for uploaded_file in uploaded_files)
    names_key = f"{state_key}_names"
    if state_key not in st.session_state or st.session_state.get(names_key) != names:
        upload_dir = Path(tempfile.mkdtemp(prefix="nextaiops_upload_"))
        paths = []
        for uploaded_file in uploaded_files:
            output_path = upload_dir / Path(str(uploaded_file.name)).name
            output_path.write_bytes(uploaded_file.getvalue())
            paths.append(output_path)
        st.session_state[state_key] = paths
        st.session_state[names_key] = names
    return cast(list[Path], st.session_state[state_key])


def _save_uploaded_file(uploaded_file: Any, state_key: str) -> Path:
    """Persist a single uploaded file and return its temp path."""
    paths = _save_uploaded_files([uploaded_file], state_key)
    return paths[0]


def _bundle_dataset_id(paths: list[Path]) -> str:
    """Return a compact display id for a multi-file upload."""
    return f"{paths[0].name}+{len(paths) - 1}" if len(paths) > 1 else paths[0].name


def _select_bundle_file(bundle: DatasetBundle, key: str, label: str) -> Table:
    """Render a file selector for DatasetBundle and return the chosen Table."""
    selected_name = st.selectbox(
        label,
        options=[dataset_file.name for dataset_file in bundle.files],
        key=key,
    )
    return next(
        dataset_file.table for dataset_file in bundle.files if dataset_file.name == selected_name
    )


def _render_filterable_dataframe(df: pd.DataFrame, key: str) -> None:
    """Render a dataframe with selectable visible columns."""
    columns = list(df.columns)
    selected_columns = st.multiselect(
        "显示列",
        options=columns,
        default=columns,
        key=f"{key}_columns",
    )
    if selected_columns:
        st.dataframe(df[selected_columns], width="stretch", hide_index=True)
    else:
        st.dataframe(df, width="stretch", hide_index=True)


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

    chart_tab, schema_tab, sample_tab = st.tabs(["指标曲线", "字段质量", "数据样例"])

    with chart_tab:
        metric_options = list(profile.metric_columns)
        selected_metric = st.selectbox(
            "预览指标",
            options=metric_options,
            key="preview_metric",
        )
        preview_fig = render_data_preview(table, metric_name=selected_metric)
        st.plotly_chart(
            preview_fig,
            width="stretch",
            config=_plotly_config(),
        )

    with schema_tab:
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
        _render_filterable_dataframe(mapping_df, key="preview_schema")

    with sample_tab:
        _render_filterable_dataframe(table.df.head(20), key="preview_sample")


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


def _render_single_result(result_artifacts_path: str, metrics: dict[str, float]) -> None:
    """Render explainable single-run result summary."""
    diagnostics_path = Path(result_artifacts_path) / "diagnostics.json"
    if diagnostics_path.exists():
        diagnostics = json.loads(diagnostics_path.read_text())
        st.subheader("检测数量摘要")
        count_cols = st.columns(4)
        count_cols[0].metric("真实异常点", diagnostics.get("true_anomalies", 0))
        count_cols[1].metric("算法检出点", diagnostics.get("predicted_anomalies", 0))
        count_cols[2].metric("命中 TP", diagnostics.get("tp", 0))
        count_cols[3].metric("误报 FP", diagnostics.get("fp", 0))

        miss_cols = st.columns(4)
        miss_cols[0].metric("漏检 FN", diagnostics.get("fn", 0))
        miss_cols[1].metric("正常 TN", diagnostics.get("tn", 0))
        miss_cols[2].metric("真实异常段", diagnostics.get("true_segments", 0))
        miss_cols[3].metric("命中异常段", diagnostics.get("hit_segments", 0))
    else:
        st.info("当前实验没有 diagnostics.json，无法展示检测数量摘要。")

    st.subheader("评估指标")
    metrics_df = pd.DataFrame(
        [
            {
                "指标": display_name,
                "值": round(metrics.get(metric_name, 0.0), 4),
                "含义": description,
            }
            for metric_name, display_name, description in _metric_explanations()
            if metric_name in metrics
        ]
    )
    _render_filterable_dataframe(
        metrics_df, key=f"single_metrics_{Path(result_artifacts_path).name}"
    )


def _metric_explanations() -> list[tuple[str, str, str]]:
    """Return metric display names and explanations."""
    return [
        ("precision", "Precision", "检出的异常中有多少是真的，越高说明误报越少"),
        ("recall", "Recall", "真实异常中有多少被检出，越高说明漏报越少"),
        ("f1", "F1", "Precision 与 Recall 的综合平衡"),
        ("pa_precision", "PA-Precision", "按异常段调整后的 Precision"),
        ("pa_recall", "PA-Recall", "按异常段调整后的 Recall"),
        ("pa_f1", "PA-F1", "按异常段调整后的 F1，更贴近运维场景"),
    ]


def _plotly_config() -> dict[str, object]:
    """Return shared Plotly interaction config."""
    return {
        "displaylogo": False,
        "scrollZoom": True,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    }


def _render_single_experiment(
    upload_ok: bool,
    input_table: Table | None,
    data_source: str,
    input_bundle: DatasetBundle | None,
) -> None:
    """Render single algorithm experiment page."""
    if not upload_ok:
        st.info("请先在侧边栏选择或上传数据")
        return

    st.header("单算法实验")

    algo_names = list_algorithms()
    if not algo_names:
        st.warning("无可用算法")
        return

    config_col, result_col = st.columns([0.32, 0.68], gap="large")

    with config_col:
        st.subheader("实验配置")
        selected_algo = st.selectbox("选择算法", algo_names)
        params = _render_param_form(selected_algo)
        if params is None:
            return

        if st.button("跑实验", type="primary", width="stretch"):
            with st.spinner("实验运行中..."):
                try:
                    if input_bundle is None:
                        result = run_experiment(
                            dataset_path=data_source,
                            algorithm_name=selected_algo,
                            params=params,
                        )
                        st.session_state["last_result"] = result
                        st.session_state.pop("last_bundle_result", None)
                        st.success(f"实验完成! run_id={result.run_id}")
                    else:
                        progress_bar = st.progress(0.0)
                        progress_text = st.empty()

                        def update_bundle_progress(index: int, total: int, file_name: str) -> None:
                            progress_bar.progress((index - 1) / total)
                            progress_text.caption(f"正在运行 {index}/{total}：{file_name}")

                        bundle_result = run_bundle_experiment(
                            bundle=input_bundle,
                            algorithm_name=selected_algo,
                            params=params,
                            progress_callback=update_bundle_progress,
                        )
                        progress_bar.progress(1.0)
                        progress_text.caption(
                            f"已完成 {len(bundle_result.file_results)}/"
                            f"{len(input_bundle.files)} 个文件"
                        )
                        st.session_state["last_bundle_result"] = bundle_result
                        st.session_state.pop("last_result", None)
                        st.success(
                            f"数据集实验完成! bundle_id={bundle_result.bundle_id}, "
                            f"文件数={len(bundle_result.file_results)}"
                        )
                except SchemaValidationError as e:
                    st.error(f"Schema 校验失败：{e}")
                except Exception as e:
                    st.error(f"实验运行失败：{e}")

    with result_col:
        st.subheader("实验结果")
        if "last_bundle_result" in st.session_state:
            bundle_result = cast(BundleRunResult, st.session_state["last_bundle_result"])
            _render_bundle_result(bundle_result)
        elif "last_result" in st.session_state:
            result = st.session_state["last_result"]
            st.caption(f"run_id: {result.run_id}")

            _render_single_result(result.artifacts_path, result.metrics)

            viz_path = Path(result.artifacts_path) / "viz.html"
            if viz_path.exists():
                st.iframe(viz_path, width="stretch", height=720)
            else:
                st.warning("viz.html 未生成")
        else:
            st.info("运行实验后将在这里展示检测摘要、指标解释和结果曲线。")


def _render_bundle_result(bundle_result: BundleRunResult) -> None:
    """Render aggregate and per-file results for a DatasetBundle experiment."""
    st.caption(f"bundle_id: {bundle_result.bundle_id} · dataset: {bundle_result.dataset_id}")

    st.subheader("数据集汇总")
    summary_cols = st.columns(4)
    summary_cols[0].metric("文件数", int(bundle_result.metrics.get("file_count", 0)))
    summary_cols[1].metric("Mean F1", f"{bundle_result.metrics.get('f1', 0.0):.4f}")
    summary_cols[2].metric("Mean PA-F1", f"{bundle_result.metrics.get('pa_f1', 0.0):.4f}")
    summary_cols[3].metric("算法", bundle_result.algorithm_name)

    rows = []
    for file_result in bundle_result.file_results:
        metrics = file_result.run_result.metrics
        rows.append(
            {
                "文件": file_result.file_name,
                "run_id": file_result.run_result.run_id,
                "F1": round(metrics.get("f1", 0.0), 4),
                "PA-F1": round(metrics.get("pa_f1", 0.0), 4),
                "Precision": round(metrics.get("precision", 0.0), 4),
                "Recall": round(metrics.get("recall", 0.0), 4),
            }
        )
    _render_filterable_dataframe(pd.DataFrame(rows), key=f"bundle_rows_{bundle_result.bundle_id}")

    selected_run_id = st.selectbox(
        "结果文件",
        options=[file_result.run_result.run_id for file_result in bundle_result.file_results],
        format_func=lambda run_id: next(
            file_result.file_name
            for file_result in bundle_result.file_results
            if file_result.run_result.run_id == run_id
        ),
    )
    selected_result = next(
        file_result.run_result
        for file_result in bundle_result.file_results
        if file_result.run_result.run_id == selected_run_id
    )
    _render_single_result(selected_result.artifacts_path, selected_result.metrics)
    viz_path = Path(selected_result.artifacts_path) / "viz.html"
    if viz_path.exists():
        st.iframe(viz_path, width="stretch", height=720)
    else:
        st.warning("viz.html 未生成")


def _render_batch_experiment(
    upload_ok: bool,
    input_table: Table | None,
    data_source: str,
    input_bundle: DatasetBundle | None,
) -> None:
    """Render batch experiment page with leaderboard, overlay, heatmap tabs."""
    if not upload_ok:
        st.info("请先在侧边栏选择或上传数据")
        return

    st.header("批量实验")

    from nextaiops_algo.algorithms.registry import REGISTRY
    from nextaiops_algo.pipeline.batch import run_batch
    from nextaiops_algo.pipeline.batch_bundle import run_batch_bundle
    from nextaiops_algo.viz.batch_bundle import (
        build_file_batch_view,
        render_bundle_algorithm_leaderboard,
        render_bundle_file_matrix,
        render_bundle_heatmap,
    )
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

    if input_bundle is not None:
        task_count = len(selected_algos) * input_bundle.file_count
        st.caption(
            f"DatasetBundle：{input_bundle.dataset_id} · "
            f"{input_bundle.file_count} 个文件 · {len(selected_algos)} 个算法 · "
            f"{task_count} 个实验单元"
        )
    else:
        st.caption(f"单文件批量：{len(selected_algos)} 个算法")

    tsbuad_algos = ["iforest", "lof", "ocsvm", "pca", "hbos"]
    has_tsbuad = any(a in algo_names for a in tsbuad_algos)
    if not has_tsbuad:
        st.info("安装 `nextaiops-algo[tsbuad]` 可解锁更多算法 (IForest, LOF, OCSVM, PCA, HBOS)")

    if st.button("开始批量实验", type="primary"):
        try:
            if input_bundle is None:
                with st.spinner(f"批量运行 {len(selected_algos)} 个算法..."):
                    batch = run_batch(
                        dataset=data_source,
                        algorithms=selected_algos,
                    )
                    st.session_state["last_batch"] = batch
                    st.session_state["batch_input_table"] = input_table
                    st.session_state.pop("last_batch_bundle", None)
                    st.success(f"批量实验完成! batch_id={batch.batch_id}, 状态={batch.status.value}")
            else:
                progress_bar = st.progress(0.0)
                progress_text = st.empty()

                def update_batch_bundle_progress(
                    index: int,
                    total: int,
                    algorithm_name: str,
                    file_name: str,
                ) -> None:
                    progress_bar.progress((index - 1) / total)
                    progress_text.caption(
                        f"正在运行 {index}/{total}：{algorithm_name} × {file_name}"
                    )

                with st.spinner(f"批量运行 {task_count} 个实验单元..."):
                    batch_bundle = run_batch_bundle(
                        bundle=input_bundle,
                        algorithms=selected_algos,
                        progress_callback=update_batch_bundle_progress,
                    )
                    progress_bar.progress(1.0)
                    progress_text.caption(
                        f"已完成 {len(batch_bundle.cells)}/{task_count} 个实验单元"
                    )
                    st.session_state["last_batch_bundle"] = batch_bundle
                    st.session_state["batch_input_bundle"] = input_bundle
                    st.session_state.pop("last_batch", None)
                    st.success(
                        f"批量数据集实验完成! id={batch_bundle.batch_bundle_id}, "
                        f"状态={batch_bundle.status.value}"
                    )
        except Exception as e:
            st.error(f"批量实验失败：{e}")

    if "last_batch_bundle" in st.session_state:
        batch_bundle = cast(BatchBundleResult, st.session_state["last_batch_bundle"])
        batch_input_bundle = cast(DatasetBundle | None, st.session_state.get("batch_input_bundle"))
        _render_batch_bundle_result(
            batch_bundle=batch_bundle,
            input_bundle=batch_input_bundle,
            render_bundle_algorithm_leaderboard=render_bundle_algorithm_leaderboard,
            render_bundle_file_matrix=render_bundle_file_matrix,
            render_bundle_heatmap=render_bundle_heatmap,
            build_file_batch_view=build_file_batch_view,
            render_overlay=render_overlay,
        )
    elif "last_batch" in st.session_state:
        batch = st.session_state["last_batch"]
        batch_input = st.session_state.get("batch_input_table")

        tab1, tab2, tab3 = st.tabs(["排行榜", "时序叠加对比", "热力图"])

        with tab1:
            store = SqliteTrackingStore()
            lb_df = render_leaderboard(batch, store=store)
            _render_filterable_dataframe(lb_df, key=f"batch_leaderboard_{batch.batch_id}")

        with tab2:
            if batch_input is not None:
                fig = render_overlay(batch, batch_input)
                st.plotly_chart(fig, width="stretch", config=_plotly_config())
            else:
                st.warning("原始数据不可用，无法渲染时序叠加")

        with tab3:
            store = SqliteTrackingStore()
            hm_fig = render_heatmap(batch, store=store)
            st.plotly_chart(hm_fig, width="stretch", config=_plotly_config())

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
            _render_filterable_dataframe(
                lb_df,
                key=f"history_batch_leaderboard_{selected_batch.batch_id}",
            )

        with tab3:
            hm_fig = render_heatmap(selected_batch, store=store)
            st.plotly_chart(hm_fig, width="stretch", config=_plotly_config())
    else:
        st.info("暂无历史批量实验记录")


def _render_batch_bundle_result(
    batch_bundle: BatchBundleResult,
    input_bundle: DatasetBundle | None,
    render_bundle_algorithm_leaderboard: Any,
    render_bundle_file_matrix: Any,
    render_bundle_heatmap: Any,
    build_file_batch_view: Any,
    render_overlay: Any,
) -> None:
    """Render DatasetBundle batch result with matrix-oriented drill-downs."""
    st.subheader("批量数据集结果")
    st.caption(
        f"id: {batch_bundle.batch_bundle_id} · dataset: {batch_bundle.dataset_id} · "
        f"状态: {batch_bundle.status.value} · summary: {batch_bundle.artifacts_path}"
    )

    summary_cols = st.columns(4)
    summary_cols[0].metric("算法数", len(batch_bundle.algorithm_names))
    summary_cols[1].metric("文件数", len(batch_bundle.file_names))
    summary_cols[2].metric(
        "成功单元",
        sum(1 for cell in batch_bundle.cells if cell.status == RunStatus.COMPLETED),
    )
    summary_cols[3].metric(
        "失败单元",
        sum(1 for cell in batch_bundle.cells if cell.status == RunStatus.FAILED),
    )

    tab1, tab2, tab3, tab4 = st.tabs(["总排行榜", "算法×文件矩阵", "文件钻取", "Cell 明细"])

    with tab1:
        leaderboard_df = render_bundle_algorithm_leaderboard(batch_bundle)
        _render_filterable_dataframe(
            leaderboard_df,
            key=f"batch_bundle_leaderboard_{batch_bundle.batch_bundle_id}",
        )

    with tab2:
        metric = st.selectbox(
            "矩阵指标",
            options=["pa_f1", "f1", "precision", "recall", "pa_precision", "pa_recall"],
            key=f"batch_bundle_metric_{batch_bundle.batch_bundle_id}",
        )
        matrix_df = render_bundle_file_matrix(batch_bundle, metric=metric)
        st.dataframe(matrix_df, width="stretch")
        heatmap_fig = render_bundle_heatmap(batch_bundle, metric=metric)
        st.plotly_chart(heatmap_fig, width="stretch", config=_plotly_config())

    with tab3:
        selected_file = st.selectbox(
            "选择文件",
            options=batch_bundle.file_names,
            key=f"batch_bundle_file_{batch_bundle.batch_bundle_id}",
        )
        if input_bundle is None:
            st.warning("当前会话没有保留原始 DatasetBundle，无法渲染文件叠加图。")
        else:
            selected_table = next(
                dataset_file.table
                for dataset_file in input_bundle.files
                if dataset_file.name == selected_file
            )
            file_batch = build_file_batch_view(batch_bundle, selected_file)
            if file_batch.runs:
                overlay_fig = render_overlay(file_batch, selected_table)
                st.plotly_chart(overlay_fig, width="stretch", config=_plotly_config())
            else:
                st.warning("该文件没有成功运行的算法，无法渲染叠加图。")

    with tab4:
        rows = []
        for cell in batch_bundle.cells:
            metrics = cell.run_result.metrics if cell.run_result is not None else {}
            rows.append(
                {
                    "算法": cell.algorithm_name,
                    "文件": cell.file_name,
                    "状态": cell.status.value,
                    "run_id": cell.run_result.run_id if cell.run_result is not None else "",
                    "F1": round(metrics.get("f1", 0.0), 4) if metrics else None,
                    "PA-F1": round(metrics.get("pa_f1", 0.0), 4) if metrics else None,
                    "错误": cell.error_message or "",
                }
            )
        _render_filterable_dataframe(
            pd.DataFrame(rows),
            key=f"batch_bundle_cells_{batch_bundle.batch_bundle_id}",
        )


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
        _render_filterable_dataframe(pd.DataFrame(history_data), key="history_runs")

        run_label_map = {r.run_id: f"{r.run_id} — {r.algorithm_name}" for r in runs}
        selected_run_id = st.selectbox(
            "查看历史实验可视化",
            options=list(run_label_map.keys()),
            format_func=lambda rid: run_label_map[rid],
        )
        selected_run = next(r for r in runs if r.run_id == selected_run_id)
        viz_path = Path(selected_run.artifacts_path) / "viz.html"
        if viz_path.exists():
            st.iframe(viz_path, width="stretch", height=600)
    else:
        st.info("暂无历史实验记录")


# ── Sidebar: page selection ─────────────────────────────────
page = st.sidebar.radio("功能页面", ["单算法实验", "批量实验", "历史记录"])

# ── Shared: data source ─────────────────────────────────────
upload_ok, input_table, data_source_desc, input_bundle = _get_input_table()

if upload_ok and input_table is not None:
    preview_table = input_table
    if input_bundle is not None:
        st.info(
            f"已加载 DatasetBundle：{input_bundle.dataset_id}，"
            f"共 {input_bundle.file_count} 个文件。"
        )
        preview_table = _select_bundle_file(
            input_bundle,
            key="bundle_preview_file",
            label="预览文件",
        )

    metric_cols = preview_table.schema.columns_of(FieldRole.METRIC)
    if len(metric_cols) > 1:
        st.info(f"检测到 {len(metric_cols)} 个 METRIC 列：{', '.join(metric_cols)}")

    _render_data_preview(preview_table)

# ── Page routing ────────────────────────────────────────────
if page == "单算法实验":
    _render_single_experiment(upload_ok, input_table, data_source_desc, input_bundle)
elif page == "批量实验":
    _render_batch_experiment(upload_ok, input_table, data_source_desc, input_bundle)
elif page == "历史记录":
    _render_history()
