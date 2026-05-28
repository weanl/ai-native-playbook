"""Streamlit UI for NextAIOpsAlgoApp — data upload, algorithm run, batch experiment, visualization."""

import json
import tempfile
from datetime import datetime
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
from nextaiops_algo.pipeline.rolling import (
    AlgorithmConfig,
    ExperimentPolicy,
    RollingExperimentResult,
    run_rolling_experiment,
)
from nextaiops_algo.pipeline.rolling_data import (
    DayPartition,
    PartitionStatus,
    build_day_partitions,
)
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
    input_disabled = _is_batch_run_in_progress()
    data_source = st.sidebar.selectbox(
        "数据来源",
        ["上传 CSV", "上传 .out", "上传 npy/npz", "上传 zip"] + list_builtin(),
        disabled=input_disabled,
    )
    if input_disabled:
        st.sidebar.caption("批量实验运行中，数据输入已临时锁定。")

    if data_source == "上传 CSV":
        uploaded_files = st.file_uploader(
            "上传指标数据 CSV",
            type=["csv"],
            accept_multiple_files=True,
            key="csv_upload",
            disabled=input_disabled,
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
            disabled=input_disabled,
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
            disabled=input_disabled,
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
        uploaded_file = st.file_uploader(
            "上传数据集 zip",
            type=["zip"],
            key="zip_upload",
            disabled=input_disabled,
        )
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
        disabled=_is_batch_run_in_progress(),
    )
    if _is_batch_run_in_progress():
        st.caption("批量实验运行中，预览文件选择已临时锁定。")
    return next(
        dataset_file.table for dataset_file in bundle.files if dataset_file.name == selected_name
    )


def _is_batch_run_in_progress() -> bool:
    """Return whether a batch experiment is currently running in this session."""
    return bool(st.session_state.get("batch_run_in_progress", False))


def _request_batch_run(payload: dict[str, Any]) -> None:
    """Mark a batch run request before Streamlit reruns the script."""
    st.session_state["batch_run_payload"] = payload
    st.session_state["batch_run_requested"] = True
    st.session_state["batch_run_in_progress"] = True


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

    if not upload_ok:
        st.info("请先在侧边栏选择或上传数据。已有批量实验结果会继续保留在下方。")

    _render_batch_run_notice()

    st.subheader("选择算法")
    batch_controls_disabled = _is_batch_run_in_progress()
    select_all = st.checkbox("全选", value=True, disabled=batch_controls_disabled)

    selected_algos: list[str] = []
    for algo in algo_names:
        if st.checkbox(
            algo,
            value=select_all,
            key=f"batch_algo_{algo}",
            disabled=batch_controls_disabled,
        ):
            selected_algos.append(algo)

    pending_batch_request = bool(st.session_state.get("batch_run_requested", False))
    if not selected_algos and not pending_batch_request:
        st.warning("请至少选择一个算法")
        _render_existing_batch_results(
            render_leaderboard=render_leaderboard,
            render_heatmap=render_heatmap,
            render_overlay=render_overlay,
            render_bundle_algorithm_leaderboard=render_bundle_algorithm_leaderboard,
            render_bundle_file_matrix=render_bundle_file_matrix,
            render_bundle_heatmap=render_bundle_heatmap,
            build_file_batch_view=build_file_batch_view,
        )
        _render_batch_history(render_leaderboard=render_leaderboard, render_heatmap=render_heatmap)
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

    default_name = _default_batch_experiment_name(
        data_source=data_source,
        input_bundle=input_bundle,
        selected_algos=selected_algos,
    )
    experiment_name = st.text_input(
        "实验名称",
        value=default_name,
        help="建议保留时间、数据和算法范围，方便在多次批量实验之间区分。",
        key="batch_experiment_name",
        disabled=batch_controls_disabled,
    )
    experiment_description = st.text_area(
        "实验描述",
        value="",
        height=80,
        help="可记录本次实验目的、数据选择原因或参数假设。",
        key="batch_experiment_description",
        disabled=batch_controls_disabled,
    )

    request_payload: dict[str, Any] = {
        "input_table": input_table,
        "input_bundle": input_bundle,
        "data_source": data_source,
        "selected_algos": list(selected_algos),
        "task_count": task_count if input_bundle is not None else len(selected_algos),
        "default_name": default_name,
        "experiment_name": experiment_name.strip() or default_name,
        "description": experiment_description.strip(),
    }
    run_disabled = not upload_ok or _is_batch_run_in_progress()
    st.button(
        "开始批量实验",
        type="primary",
        disabled=run_disabled,
        on_click=_request_batch_run,
        args=(request_payload,),
    )
    should_run_batch = bool(st.session_state.pop("batch_run_requested", False))
    if should_run_batch:
        payload = cast(dict[str, Any], st.session_state.get("batch_run_payload", {}))
        run_table_snapshot = cast(Table | None, payload.get("input_table"))
        run_bundle_snapshot = cast(DatasetBundle | None, payload.get("input_bundle"))
        run_data_source = str(payload.get("data_source", ""))
        run_algos = cast(list[str], payload.get("selected_algos", []))
        run_task_count = int(payload.get("task_count", len(run_algos)))
        run_experiment_name = str(payload.get("experiment_name", default_name))
        run_description = str(payload.get("description", ""))
        try:
            if run_bundle_snapshot is None:
                with st.spinner(f"批量运行 {len(run_algos)} 个算法..."):
                    batch = run_batch(
                        dataset=run_data_source,
                        algorithms=run_algos,
                    )
                    st.session_state["last_batch"] = batch
                    st.session_state["batch_input_table"] = run_table_snapshot
                    st.session_state["last_batch_meta"] = {
                        "experiment_name": run_experiment_name,
                        "description": run_description,
                        "data_source": run_data_source,
                        "algorithm_scope": ", ".join(run_algos),
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    st.session_state.pop("last_batch_bundle", None)
                    st.session_state["batch_run_notice"] = (
                        "success",
                        f"批量实验完成! batch_id={batch.batch_id}, 状态={batch.status.value}",
                    )
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

                with st.spinner(f"批量运行 {run_task_count} 个实验单元..."):
                    batch_bundle = run_batch_bundle(
                        bundle=run_bundle_snapshot,
                        algorithms=run_algos,
                        experiment_name=run_experiment_name,
                        description=run_description,
                        progress_callback=update_batch_bundle_progress,
                    )
                    progress_bar.progress(1.0)
                    progress_text.caption(
                        f"已完成 {len(batch_bundle.cells)}/{run_task_count} 个实验单元"
                    )
                    st.session_state["last_batch_bundle"] = batch_bundle
                    st.session_state["batch_input_bundle"] = run_bundle_snapshot
                    st.session_state.pop("last_batch", None)
                    st.session_state["batch_run_notice"] = (
                        "success",
                        f"批量数据集实验完成! id={batch_bundle.batch_bundle_id}, "
                        f"状态={batch_bundle.status.value}",
                    )
        except Exception as e:
            st.session_state["batch_run_notice"] = ("error", f"批量实验失败：{e}")
        finally:
            st.session_state["batch_run_in_progress"] = False
            st.session_state.pop("batch_run_payload", None)
            st.rerun()

    _render_existing_batch_results(
        render_leaderboard=render_leaderboard,
        render_heatmap=render_heatmap,
        render_overlay=render_overlay,
        render_bundle_algorithm_leaderboard=render_bundle_algorithm_leaderboard,
        render_bundle_file_matrix=render_bundle_file_matrix,
        render_bundle_heatmap=render_bundle_heatmap,
        build_file_batch_view=build_file_batch_view,
    )
    _render_batch_history(render_leaderboard=render_leaderboard, render_heatmap=render_heatmap)


def _render_batch_run_notice() -> None:
    """Render and clear the latest batch run completion notice."""
    notice = st.session_state.pop("batch_run_notice", None)
    if notice is None:
        return
    level, message = cast(tuple[str, str], notice)
    if level == "success":
        st.success(message)
    else:
        st.error(message)


def _default_batch_experiment_name(
    data_source: str,
    input_bundle: DatasetBundle | None,
    selected_algos: list[str],
) -> str:
    """Build a readable default batch experiment name."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    dataset_label = input_bundle.dataset_id if input_bundle is not None else Path(data_source).name
    if len(selected_algos) <= 3:
        algorithm_scope = ",".join(selected_algos)
    else:
        algorithm_scope = f"{selected_algos[0]}+{len(selected_algos) - 1}"
    return f"{timestamp} · {dataset_label} · {algorithm_scope}"


def _render_existing_batch_results(
    render_leaderboard: Any,
    render_heatmap: Any,
    render_overlay: Any,
    render_bundle_algorithm_leaderboard: Any,
    render_bundle_file_matrix: Any,
    render_bundle_heatmap: Any,
    build_file_batch_view: Any,
) -> None:
    """Render the latest batch result independently from the current preview input."""
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
        batch_meta = cast(dict[str, str], st.session_state.get("last_batch_meta", {}))

        if batch_meta:
            st.subheader("批量实验结果")
            st.caption(
                f"{batch_meta.get('experiment_name', batch.batch_id)} · "
                f"数据: {batch_meta.get('data_source', batch.dataset_source)} · "
                f"算法: {batch_meta.get('algorithm_scope', ', '.join(batch.algorithm_names))} · "
                f"时间: {batch_meta.get('created_at', '')}"
            )
            if batch_meta.get("description"):
                st.info(batch_meta["description"])

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


def _render_batch_history(render_leaderboard: Any, render_heatmap: Any) -> None:
    """Render persisted single-file batch history."""
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
        f"{batch_bundle.experiment_name} · id: {batch_bundle.batch_bundle_id} · "
        f"dataset: {batch_bundle.dataset_id} · "
        f"状态: {batch_bundle.status.value} · summary: {batch_bundle.artifacts_path}"
    )
    if batch_bundle.description:
        st.info(batch_bundle.description)

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


def _build_partition_dataframe(partitions: list[DayPartition]) -> pd.DataFrame:
    """Build a display dataframe for rolling day partition quality."""
    return pd.DataFrame(
        [
            {
                "日期": partition.date.isoformat(),
                "行数": partition.row_count,
                "有标签": "是" if partition.has_label else "否",
                "标签覆盖率": (
                    "" if partition.label_coverage is None else f"{partition.label_coverage:.2%}"
                ),
                "状态": partition.status.value,
                "排除原因": (
                    "" if partition.exclusion_reason is None else partition.exclusion_reason.value
                ),
            }
            for partition in partitions
        ]
    )


def _rolling_valid_partitions(partitions: list[DayPartition]) -> list[DayPartition]:
    """Return partitions that can participate in a rolling experiment."""
    return [partition for partition in partitions if partition.status == PartitionStatus.VALID]


def _build_cycle_dataframe(result: RollingExperimentResult) -> pd.DataFrame:
    """Build a display dataframe for rolling day cycles."""
    return pd.DataFrame(
        [
            {
                "cutoff_day": cycle.cutoff_day.isoformat(),
                "算法": cycle.algorithm_name,
                "train_rows": cycle.train_rows,
                "validate_rows": cycle.validate_rows,
                "active_start": _optional_display(cycle.active_interval_start),
                "active_end": _optional_display(cycle.active_interval_end),
                "状态": cycle.status,
                "active_model_id": cycle.active_model_id or "",
                "PA-F1": _round_optional(cycle.metrics.get("pa_f1")),
                "错误": cycle.error_message or cycle.exclusion_reason or "",
            }
            for cycle in result.cycles
        ]
    )


def _build_leaderboard_dataframe(result: RollingExperimentResult) -> pd.DataFrame:
    """Build a display dataframe for rolling leaderboard rows."""
    return pd.DataFrame(
        [
            {
                "算法": row.algorithm_name,
                "参数": json.dumps(row.params, ensure_ascii=False),
                "Mean PA-F1": round(row.mean_pa_f1, 4),
                "Median PA-F1": round(row.median_pa_f1, 4),
                "success_rate": f"{row.success_rate:.2%}",
                "完成 cycles": row.cycles_completed,
                "失败 cycles": row.cycles_failed,
            }
            for row in result.leaderboard
        ]
    )


def _build_ledger_dataframe(result: RollingExperimentResult, limit: int = 200) -> pd.DataFrame:
    """Build a preview dataframe for rolling prediction ledger rows."""
    return pd.DataFrame(
        [
            {
                "timestamp": str(row.timestamp),
                "算法": row.algorithm_name,
                "cutoff_day": row.cutoff_day.isoformat(),
                "active_model_id": row.active_model_id,
                "predicted_label": row.predicted_label,
                "score": _round_optional(row.score),
                "label": row.label,
            }
            for row in result.ledger[:limit]
        ]
    )


def _build_active_timeline_dataframe(result: RollingExperimentResult) -> pd.DataFrame:
    """Build a display dataframe for active model intervals."""
    return pd.DataFrame(
        [
            {
                "cutoff_day": cycle.cutoff_day.isoformat(),
                "算法": cycle.algorithm_name,
                "active_start": _optional_display(cycle.active_interval_start),
                "active_end": _optional_display(cycle.active_interval_end),
                "active_model_id": cycle.active_model_id or "",
                "状态": cycle.status,
            }
            for cycle in result.cycles
            if cycle.active_model_id is not None or cycle.status == "blocked"
        ]
    )


def _build_exclusion_dataframe(
    partitions: list[DayPartition],
    result: RollingExperimentResult | None,
) -> pd.DataFrame:
    """Build a dataframe for invalid partitions, blocked intervals, and failures."""
    rows: list[dict[str, object]] = []
    for partition in partitions:
        if partition.status != PartitionStatus.VALID:
            rows.append(
                {
                    "类型": "invalid_partition",
                    "日期/cutoff": partition.date.isoformat(),
                    "算法": "",
                    "原因": (
                        ""
                        if partition.exclusion_reason is None
                        else partition.exclusion_reason.value
                    ),
                }
            )
    if result is not None:
        for cycle in result.cycles:
            if cycle.status != "completed":
                rows.append(
                    {
                        "类型": cycle.status,
                        "日期/cutoff": cycle.cutoff_day.isoformat(),
                        "算法": cycle.algorithm_name,
                        "原因": cycle.error_message or cycle.exclusion_reason or "",
                    }
                )
    return pd.DataFrame(rows)


def _rolling_policy_signature(
    *,
    data_source: str,
    date_column: str | None,
    selected_algorithms: list[str],
    algorithm_params: dict[str, dict[str, object]],
    policy: ExperimentPolicy,
) -> str:
    """Return a stable signature for the frozen rolling policy."""
    payload = {
        "data_source": data_source,
        "date_column": date_column,
        "selected_algorithms": selected_algorithms,
        "algorithm_params": algorithm_params,
        "policy": policy.model_dump(mode="json"),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _round_optional(value: float | None) -> float | None:
    """Round a numeric value for compact display."""
    return None if value is None else round(float(value), 4)


def _optional_display(value: object) -> str:
    """Format optional datetime-like values for tables."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _render_rolling_workbench(
    upload_ok: bool,
    input_table: Table | None,
    data_source: str,
    input_bundle: DatasetBundle | None,
) -> None:
    """Render the rolling experiment MVP workbench."""
    st.header("滚动实验工作台")
    access_tab, preview_tab, config_tab, task_tab, result_tab = st.tabs(
        ["数据接入", "数据预览", "实验配置", "实验任务管理", "实验结果查看"]
    )

    threshold_key = "rolling_label_coverage_threshold"
    validate_key = "rolling_validate_ratio"

    with access_tab:
        st.subheader("数据接入")
        if not upload_ok or input_table is None:
            st.info("请先在侧边栏选择或上传数据。")
            return

        st.caption(f"当前数据源：{data_source}")
        if input_bundle is not None:
            st.warning(
                "当前输入是 DatasetBundle。M2-027 MVP 可展示首个文件的分区诊断，"
                "但滚动实验执行仍需单文件路径或内置数据集名。"
            )

        date_options = ["自动识别"] + list(input_table.df.columns)
        selected_date = st.selectbox(
            "日期/时间列",
            options=date_options,
            help="默认使用 schema 中的 TIMESTAMP 角色；如需覆盖，可选择具体列。",
            key="rolling_date_column",
        )
        date_column = None if selected_date == "自动识别" else str(selected_date)

        label_threshold = st.number_input(
            "label coverage 门槛",
            min_value=0.0,
            max_value=1.0,
            value=float(st.session_state.get(threshold_key, 0.0)),
            step=0.05,
            key=threshold_key,
        )

        try:
            partitions = build_day_partitions(
                input_table,
                date_column=date_column,
                threshold=label_threshold,
            )
        except ValueError as e:
            st.error(f"无法构建日分区：{e}")
            st.session_state["rolling_partitions"] = []
            return

        st.session_state["rolling_partitions"] = partitions
        valid_partitions = _rolling_valid_partitions(partitions)
        summary_cols = st.columns(4)
        summary_cols[0].metric("总分区", len(partitions))
        summary_cols[1].metric("有效分区", len(valid_partitions))
        summary_cols[2].metric("无效分区", len(partitions) - len(valid_partitions))
        summary_cols[3].metric("总行数", sum(partition.row_count for partition in partitions))

        _render_filterable_dataframe(
            _build_partition_dataframe(partitions),
            key="rolling_partitions",
        )
        if len(valid_partitions) < 2:
            st.warning("滚动实验至少需要 2 个有效日分区：前一日训练，后一日 active 推理。")

    with preview_tab:
        st.subheader("数据预览")
        if not upload_ok or input_table is None:
            st.info("请先在侧边栏选择或上传数据。")
        else:
            _render_data_preview(input_table)
            partitions = cast(list[DayPartition], st.session_state.get("rolling_partitions", []))
            if partitions:
                st.subheader("日分区质量")
                _render_filterable_dataframe(
                    _build_partition_dataframe(partitions),
                    key="rolling_preview_partitions",
                )

    with config_tab:
        st.subheader("实验配置")
        if not upload_ok or input_table is None:
            st.info("请先在侧边栏选择或上传数据。")
            return

        algo_names = list_algorithms()
        default_algos = algo_names[: min(2, len(algo_names))]
        selected_algorithms = st.multiselect(
            "选择算法",
            options=algo_names,
            default=default_algos,
            key="rolling_algorithms",
        )
        if not selected_algorithms:
            st.warning("请至少选择一个算法。")

        algorithm_params: dict[str, dict[str, object]] = {}
        with st.expander("算法参数 JSON（可选）"):
            for algorithm_name in selected_algorithms:
                params_text = st.text_area(
                    f"{algorithm_name} 参数",
                    value="{}",
                    key=f"rolling_params_{algorithm_name}",
                )
                try:
                    params = json.loads(params_text)
                except json.JSONDecodeError as e:
                    st.error(f"{algorithm_name} 参数 JSON 格式错误：{e}")
                    return
                if not isinstance(params, dict):
                    st.error(f"{algorithm_name} 参数 JSON 必须是对象。")
                    return
                algorithm_params[algorithm_name] = cast(dict[str, object], params)

        validate_ratio = st.number_input(
            "validate_ratio",
            min_value=0.05,
            max_value=0.95,
            value=float(st.session_state.get(validate_key, 0.7)),
            step=0.05,
            key=validate_key,
        )
        policy = ExperimentPolicy(
            validate_ratio=float(validate_ratio),
            label_coverage_threshold=float(st.session_state.get(threshold_key, 0.0)),
        )

        policy_cols = st.columns(3)
        policy_cols[0].metric("cadence", policy.cadence)
        policy_cols[1].metric("auto_active", policy.auto_active)
        policy_cols[2].metric("错误策略", policy.on_algorithm_error)

        date_column = cast(str | None, st.session_state.get("rolling_date_column"))
        if date_column == "自动识别":
            date_column = None
        signature = _rolling_policy_signature(
            data_source=data_source,
            date_column=date_column,
            selected_algorithms=selected_algorithms,
            algorithm_params=algorithm_params,
            policy=policy,
        )
        frozen_signature = st.session_state.get("rolling_frozen_signature")
        if frozen_signature == signature:
            st.success("策略已冻结，可以进入任务管理运行滚动实验。")
        elif frozen_signature is not None:
            st.warning("配置已变化，请重新冻结策略。")

        if st.button("冻结策略", type="primary", disabled=not selected_algorithms):
            st.session_state["rolling_frozen_signature"] = signature
            st.session_state["rolling_frozen_payload"] = {
                "data_source": data_source,
                "date_column": date_column,
                "algorithms": selected_algorithms,
                "algorithm_params": algorithm_params,
                "policy": policy,
            }
            st.success("策略已冻结。")

    with task_tab:
        st.subheader("实验任务管理")
        partitions = cast(list[DayPartition], st.session_state.get("rolling_partitions", []))
        valid_partitions = _rolling_valid_partitions(partitions)
        frozen_payload = cast(
            dict[str, object] | None,
            st.session_state.get("rolling_frozen_payload"),
        )
        run_disabled = (
            input_bundle is not None
            or frozen_payload is None
            or len(valid_partitions) < 2
            or not upload_ok
        )
        if input_bundle is not None:
            st.info("DatasetBundle 暂不支持直接执行滚动实验，请选择单文件或内置数据集。")
        if frozen_payload is None:
            st.info("请先在实验配置 tab 冻结策略。")

        if st.button("运行滚动实验", type="primary", disabled=run_disabled) and frozen_payload is not None:
            frozen_params = cast(
                dict[str, dict[str, object]],
                frozen_payload["algorithm_params"],
            )
            frozen_algorithms = cast(list[str], frozen_payload["algorithms"])
            algorithms = [
                AlgorithmConfig(
                    name=algorithm_name,
                    params=frozen_params[algorithm_name],
                )
                for algorithm_name in frozen_algorithms
            ]
            with st.spinner("滚动实验运行中..."):
                try:
                    run_result = run_rolling_experiment(
                        cast(str, frozen_payload["data_source"]),
                        algorithms=algorithms,
                        date_column=cast(str | None, frozen_payload["date_column"]),
                        policy=cast(ExperimentPolicy, frozen_payload["policy"]),
                    )
                    st.session_state["last_rolling_result"] = run_result
                    st.success(
                        f"滚动实验完成：experiment_id={run_result.experiment.experiment_id}，"
                        f"状态={run_result.experiment.status}"
                    )
                except Exception as e:
                    st.error(f"滚动实验失败：{e}")

        task_result = cast(
            RollingExperimentResult | None,
            st.session_state.get("last_rolling_result"),
        )
        if task_result is not None:
            _render_rolling_task_summary(task_result)

    with result_tab:
        st.subheader("实验结果查看")
        display_result = cast(
            RollingExperimentResult | None,
            st.session_state.get("last_rolling_result"),
        )
        partitions = cast(list[DayPartition], st.session_state.get("rolling_partitions", []))
        if display_result is None:
            st.info("运行滚动实验后将在这里展示排行、active timeline 和 prediction ledger。")
            _render_rolling_history()
        else:
            _render_rolling_result(display_result, partitions)


def _render_rolling_task_summary(result: RollingExperimentResult) -> None:
    """Render rolling experiment task status and cycle details."""
    summary_cols = st.columns(4)
    summary_cols[0].metric("experiment_id", result.experiment.experiment_id)
    summary_cols[1].metric("状态", result.experiment.status)
    summary_cols[2].metric("cycles", len(result.cycles))
    summary_cols[3].metric("ledger rows", len(result.ledger))

    cycle_df = _build_cycle_dataframe(result)
    if not cycle_df.empty:
        _render_filterable_dataframe(cycle_df, key=f"rolling_cycles_{result.experiment.experiment_id}")

    failed = cycle_df[cycle_df["状态"] != "completed"] if not cycle_df.empty else pd.DataFrame()
    if not failed.empty:
        st.warning("存在 blocked 或 partial_failed cycle，请在结果页查看排除项汇总。")


def _render_rolling_result(
    result: RollingExperimentResult,
    partitions: list[DayPartition],
) -> None:
    """Render rolling leaderboard, active timeline, ledger, and exclusions."""
    summary_cols = st.columns(4)
    summary_cols[0].metric("cutoff cycles", len(result.cycles))
    summary_cols[1].metric(
        "active models",
        sum(1 for cycle in result.cycles if cycle.active_model_id is not None),
    )
    summary_cols[2].metric("ledger rows", len(result.ledger))
    summary_cols[3].metric("blocked", len(result.blocked_intervals))

    leaderboard_tab, timeline_tab, ledger_tab, exclusion_tab = st.tabs(
        ["算法排行", "Active Timeline", "Prediction Ledger", "排除项汇总"]
    )
    with leaderboard_tab:
        leaderboard_df = _build_leaderboard_dataframe(result)
        if leaderboard_df.empty:
            st.warning("暂无可用排行。")
        else:
            _render_filterable_dataframe(
                leaderboard_df,
                key=f"rolling_leaderboard_{result.experiment.experiment_id}",
            )

    with timeline_tab:
        timeline_df = _build_active_timeline_dataframe(result)
        if timeline_df.empty:
            st.warning("暂无 active model timeline。")
        else:
            _render_filterable_dataframe(
                timeline_df,
                key=f"rolling_timeline_{result.experiment.experiment_id}",
            )

    with ledger_tab:
        ledger_df = _build_ledger_dataframe(result)
        if ledger_df.empty:
            st.warning("暂无 prediction ledger。")
        else:
            st.caption("仅展示前 200 行。")
            _render_filterable_dataframe(
                ledger_df,
                key=f"rolling_ledger_{result.experiment.experiment_id}",
            )

    with exclusion_tab:
        exclusion_df = _build_exclusion_dataframe(partitions, result)
        if exclusion_df.empty:
            st.success("未发现 invalid partition、blocked interval 或 failed algorithm。")
        else:
            _render_filterable_dataframe(
                exclusion_df,
                key=f"rolling_exclusions_{result.experiment.experiment_id}",
            )

    _render_rolling_history()


def _render_rolling_history() -> None:
    """Render persisted rolling experiment history."""
    store = SqliteTrackingStore()
    experiments = store.list_rolling_experiments(limit=10)
    if not experiments:
        st.info("暂无历史滚动实验记录。")
        return

    history_rows = []
    for experiment in experiments:
        experiment_id = str(experiment["experiment_id"])
        history_rows.append(
            {
                "experiment_id": experiment_id,
                "数据集": experiment["dataset_path"],
                "date_column": experiment["date_column"] or "",
                "状态": experiment["status"],
                "created_at": experiment["created_at"],
                "ledger rows": store.count_rolling_predictions(experiment_id),
            }
        )
    st.subheader("历史滚动实验")
    _render_filterable_dataframe(pd.DataFrame(history_rows), key="rolling_history")


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
page = st.sidebar.radio("功能页面", ["单算法实验", "批量实验", "滚动实验工作台", "历史记录"])

# ── Shared: data source ─────────────────────────────────────
upload_ok, input_table, data_source_desc, input_bundle = _get_input_table()

if page != "滚动实验工作台" and upload_ok and input_table is not None:
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
elif page == "滚动实验工作台":
    _render_rolling_workbench(upload_ok, input_table, data_source_desc, input_bundle)
elif page == "历史记录":
    _render_history()
