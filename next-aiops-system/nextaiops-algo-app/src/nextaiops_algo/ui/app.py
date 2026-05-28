"""Streamlit UI for NextAIOpsAlgoApp — data upload, algorithm run, batch experiment, visualization."""

import json
import tempfile
from datetime import date, datetime
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
    RollingDayCycle,
    RollingExperimentResult,
    run_rolling_experiment,
)
from nextaiops_algo.pipeline.rolling_bundle import RollingBundleResult, run_rolling_bundle
from nextaiops_algo.pipeline.rolling_data import (
    DayPartition,
    PartitionStatus,
    SyntheticTimeConfig,
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
    Caches loaded Table/Bundle in session_state to avoid re-reading on every rerun
    (e.g. when a radio/selectbox in another tab triggers a Streamlit rerun).
    """
    input_disabled = _is_batch_run_in_progress()
    data_source = st.sidebar.selectbox(
        "数据来源",
        ["上传 CSV", "上传 .out", "上传 npy/npz", "上传 zip"] + list_builtin(),
        disabled=input_disabled,
    )
    if input_disabled:
        st.sidebar.caption("批量实验运行中，数据输入已临时锁定。")

    def _cache_hit(
        source: str,
        file_names: tuple[str, ...] | None = None,
    ) -> tuple[bool, Table | None, str, DatasetBundle | None] | None:
        """Return cached result if data source + files unchanged, else None."""
        prev_source = st.session_state.get("_input_cache_source")
        prev_names = st.session_state.get("_input_cache_names")
        if prev_source == source and prev_names == file_names and prev_source is not None:
            return (
                st.session_state.get("_input_cache_ok", False),
                st.session_state.get("_input_cache_table"),
                st.session_state.get("_input_cache_desc", ""),
                st.session_state.get("_input_cache_bundle"),
            )
        return None

    def _cache_store(
        ok: bool,
        table: Table | None,
        desc: str,
        bundle: DatasetBundle | None,
        source: str,
        file_names: tuple[str, ...] | None = None,
    ) -> tuple[bool, Table | None, str, DatasetBundle | None]:
        """Store result in session_state cache and return it."""
        st.session_state["_input_cache_ok"] = ok
        st.session_state["_input_cache_table"] = table
        st.session_state["_input_cache_desc"] = desc
        st.session_state["_input_cache_bundle"] = bundle
        st.session_state["_input_cache_source"] = source
        st.session_state["_input_cache_names"] = file_names
        return ok, table, desc, bundle

    if data_source == "上传 CSV":
        uploaded_files = st.file_uploader(
            "上传指标数据 CSV",
            type=["csv"],
            accept_multiple_files=True,
            key="csv_upload",
            disabled=input_disabled,
        )
        if not uploaded_files:
            return _cache_store(False, None, "", None, data_source, None)
        file_names = tuple(f.name for f in uploaded_files)
        cached = _cache_hit(data_source, file_names)
        if cached is not None:
            return cached
        upload_paths = _save_uploaded_files(cast(list[Any], uploaded_files), "csv_upload_paths")
        try:
            if len(upload_paths) == 1:
                table = read_csv_to_table(upload_paths[0])
                return _cache_store(True, table, str(upload_paths[0]), None, data_source, file_names)
            bundle = read_dataset_bundle(upload_paths, dataset_id=_bundle_dataset_id(upload_paths))
            return _cache_store(
                True, bundle.files[0].table, bundle.dataset_id, bundle, data_source, file_names
            )
        except SchemaValidationError as e:
            st.error(f"数据格式校验失败：{e}")
            return _cache_store(False, None, "", None, data_source, file_names)

    elif data_source == "上传 .out":
        uploaded_files = st.file_uploader(
            "上传 TSB-UAD .out 文件",
            type=["out"],
            accept_multiple_files=True,
            key="out_upload",
            disabled=input_disabled,
        )
        if not uploaded_files:
            return _cache_store(False, None, "", None, data_source, None)
        file_names = tuple(f.name for f in uploaded_files)
        cached = _cache_hit(data_source, file_names)
        if cached is not None:
            return cached
        upload_paths = _save_uploaded_files(cast(list[Any], uploaded_files), "out_upload_paths")
        try:
            if len(upload_paths) == 1:
                table = read_to_table(upload_paths[0])
                return _cache_store(True, table, str(upload_paths[0]), None, data_source, file_names)
            bundle = read_dataset_bundle(upload_paths, dataset_id=_bundle_dataset_id(upload_paths))
            return _cache_store(
                True, bundle.files[0].table, bundle.dataset_id, bundle, data_source, file_names
            )
        except SchemaValidationError as e:
            st.error(f"数据格式校验失败：{e}")
            return _cache_store(False, None, "", None, data_source, file_names)

    elif data_source == "上传 npy/npz":
        uploaded_files = st.file_uploader(
            "上传 npy/npz 文件",
            type=["npy", "npz"],
            accept_multiple_files=True,
            key="npy_upload",
            disabled=input_disabled,
        )
        if not uploaded_files:
            return _cache_store(False, None, "", None, data_source, None)
        file_names = tuple(f.name for f in uploaded_files)
        cached = _cache_hit(data_source, file_names)
        if cached is not None:
            return cached
        upload_paths = _save_uploaded_files(cast(list[Any], uploaded_files), "npy_upload_paths")
        try:
            if len(upload_paths) == 1:
                table = read_to_table(upload_paths[0])
                return _cache_store(True, table, str(upload_paths[0]), None, data_source, file_names)
            bundle = read_dataset_bundle(upload_paths, dataset_id=_bundle_dataset_id(upload_paths))
            return _cache_store(
                True, bundle.files[0].table, bundle.dataset_id, bundle, data_source, file_names
            )
        except SchemaValidationError as e:
            st.error(f"数据格式校验失败：{e}")
            return _cache_store(False, None, "", None, data_source, file_names)

    elif data_source == "上传 zip":
        uploaded_file = st.file_uploader(
            "上传数据集 zip",
            type=["zip"],
            key="zip_upload",
            disabled=input_disabled,
        )
        if uploaded_file is None:
            return _cache_store(False, None, "", None, data_source, None)
        file_names = (uploaded_file.name,)
        cached = _cache_hit(data_source, file_names)
        if cached is not None:
            return cached
        zip_path = _save_uploaded_file(cast(Any, uploaded_file), "zip_upload_path")
        extract_dir = Path(tempfile.mkdtemp(prefix="nextaiops_zip_"))
        try:
            bundle = read_dataset_bundle_from_zip(
                zip_path,
                extract_dir=extract_dir,
                dataset_id=Path(uploaded_file.name).stem,
            )
            return _cache_store(
                True, bundle.files[0].table, bundle.dataset_id, bundle, data_source, file_names
            )
        except SchemaValidationError as e:
            st.error(f"数据格式校验失败：{e}")
            return _cache_store(False, None, "", None, data_source, file_names)

    else:
        cached = _cache_hit(data_source)
        if cached is not None:
            return cached
        try:
            table = get_builtin(data_source).load()
            return _cache_store(True, table, data_source, None, data_source)
        except Exception as e:
            st.error(f"加载内置数据集失败：{e}")
            return _cache_store(False, None, "", None, data_source)


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
        ("precision", "Precision（点级）", "检出的异常点中有多少是真的，越高说明误报越少"),
        ("recall", "Recall（点级）", "真实异常点中有多少被检出，越高说明漏报越少"),
        ("f1", "F1（点级）", "Precision 与 Recall 的调和平均"),
        ("pa_precision", "PA-Precision（段调整）", "按异常段调整后的 Precision，命中段内任意一点即视为全段命中"),
        ("pa_recall", "PA-Recall（段调整）", "按异常段调整后的 Recall"),
        ("pa_f1", "PA-F1（段调整）", "按异常段调整后的 F1，更贴近运维场景"),
        ("seg_recall", "段召回率", "真实异常段中被有效检测出的比例（基于 IoU 阈值匹配）"),
        ("seg_precision", "段精确率", "检测出的异常段中有多少与真实段有效匹配（基于 IoU 阈值）"),
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
    synthetic_time: SyntheticTimeConfig | None,
    selected_algorithms: list[str],
    algorithm_params: dict[str, dict[str, object]],
    policy: ExperimentPolicy,
) -> str:
    """Return a stable signature for the frozen rolling policy."""
    payload = {
        "data_source": data_source,
        "date_column": date_column,
        "synthetic_time": None
        if synthetic_time is None
        else synthetic_time.model_dump(mode="json"),
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
            st.info(f"DatasetBundle：共 {input_bundle.file_count} 个文件，将对每个文件独立运行滚动实验。")

        time_mode = st.radio(
            "时间来源",
            options=["自动识别 timestamp", "选择日期/时间列", "用行号合成时间"],
            horizontal=True,
            key="rolling_time_mode",
        )
        date_column: str | None = None
        synthetic_time: SyntheticTimeConfig | None = None
        if time_mode == "选择日期/时间列":
            date_column = str(st.selectbox(
                "日期/时间列",
                options=list(input_table.df.columns),
                help="覆盖 schema 中的 TIMESTAMP 角色，用指定列构建日分区。",
                key="rolling_date_column",
            ))
        elif time_mode == "用行号合成时间":
            st.caption("适用于 TSB-AD-U 这类只有 value/label、没有 timestamp 的单序列数据。")
            synthetic_start_time = st.text_input(
                "合成起始时间",
                value="2024-01-01T00:00:00Z",
                key="rolling_synthetic_start_time",
            )
            synthetic_interval = st.text_input(
                "行间隔",
                value="1min",
                help="格式：Ns / Nmin / Nh，例如 30s、1min、1h。",
                key="rolling_synthetic_interval",
            )
            synthetic_time = SyntheticTimeConfig(
                time_index_column="__row_index__",
                synthetic_start_time=synthetic_start_time,
                synthetic_interval=synthetic_interval,
            )

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
                synthetic_time=synthetic_time,
            )
        except ValueError as e:
            st.error(f"无法构建日分区：{e}")
            st.session_state["rolling_partitions"] = []
            return

        st.session_state["rolling_partitions"] = partitions
        st.session_state["rolling_date_column_value"] = date_column
        st.session_state["rolling_synthetic_time"] = synthetic_time
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
            preview_table = input_table
            if input_bundle is not None and input_bundle.file_count > 1:
                total_pages = (input_bundle.file_count + 4) // 5
                page = st.number_input(
                    "文件分页",
                    min_value=1,
                    max_value=total_pages,
                    value=1,
                    step=1,
                    format="%d",
                    help=f"共 {input_bundle.file_count} 个文件，每页 5 个",
                    key="rolling_preview_page",
                )
                start = (int(page) - 1) * 5
                end = min(start + 5, input_bundle.file_count)
                page_files = input_bundle.files[start:end]
                selected_name = st.radio(
                    f"选择文件（第 {start + 1}~{end} / {input_bundle.file_count} 个）",
                    options=[f.name for f in page_files],
                    key="rolling_preview_file",
                    horizontal=True,
                )
                preview_table = next(
                    f.table for f in input_bundle.files if f.name == selected_name
                )
            _render_data_preview(preview_table)
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
        preferred_defaults = ["iqr", "three_sigma"]
        default_algos = [name for name in preferred_defaults if name in algo_names]
        if not default_algos:
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

        # 检测起始日选择器
        partitions = cast(list[DayPartition], st.session_state.get("rolling_partitions", []))
        valid_partitions = _rolling_valid_partitions(partitions)
        detect_start_day: date | None = None
        if len(valid_partitions) >= 2:
            valid_dates = [p.date for p in valid_partitions]
            # 默认选择第二个有效分区（第二天），之前的数据仅作为训练数据
            default_idx = min(1, len(valid_dates) - 1)
            selected_date = st.selectbox(
                "检测起始日（首个 cutoff day）",
                options=valid_dates,
                index=default_idx,
                help="之前的日分区仅作为训练数据，不参与滚动推理。",
                key="rolling_detect_start_day",
            )
            detect_start_day = selected_date

        segment_iou_threshold = st.slider(
            "异常段匹配 IoU 阈值",
            min_value=0.01,
            max_value=1.0,
            value=0.5,
            step=0.01,
            help="真实异常段与检测异常段的交集占并集比例 ≥ 该值时，视为有效匹配。用于计算段级召回率和精确率。",
            key="rolling_segment_iou_threshold",
        )

        policy = ExperimentPolicy(
            validate_ratio=float(validate_ratio),
            label_coverage_threshold=float(st.session_state.get(threshold_key, 0.0)),
            detect_start_day=detect_start_day,
            segment_iou_threshold=float(segment_iou_threshold),
        )

        policy_cols = st.columns(3)
        policy_cols[0].metric("cadence", policy.cadence)
        policy_cols[1].metric("auto_active", policy.auto_active)
        policy_cols[2].metric("错误策略", policy.on_algorithm_error)

        date_column = cast(str | None, st.session_state.get("rolling_date_column_value"))
        synthetic_time = cast(
            SyntheticTimeConfig | None,
            st.session_state.get("rolling_synthetic_time"),
        )
        signature = _rolling_policy_signature(
            data_source=data_source,
            date_column=date_column,
            synthetic_time=synthetic_time,
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
                "synthetic_time": synthetic_time,
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
            frozen_payload is None
            or len(valid_partitions) < 2
            or not upload_ok
        )
        if frozen_payload is None:
            st.info("请先在实验配置 tab 冻结策略。")
        if input_bundle is not None:
            st.info(f"将对 {input_bundle.file_count} 个文件分别运行滚动实验。")

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
            frozen_policy = cast(ExperimentPolicy, frozen_payload["policy"])
            frozen_date_column = cast(str | None, frozen_payload["date_column"])
            frozen_synthetic_time = cast(
                SyntheticTimeConfig | None,
                frozen_payload["synthetic_time"],
            )

            if input_bundle is not None:
                # 多文件模式：对每个文件独立运行滚动实验
                progress_placeholder = st.empty()

                def bundle_progress(current: int, total: int, file_name: str) -> None:
                    progress_placeholder.info(f"[{current}/{total}] 正在处理 {file_name}...")

                try:
                    bundle_result = run_rolling_bundle(
                        input_bundle,
                        algorithms=algorithms,
                        date_column=frozen_date_column,
                        policy=frozen_policy,
                        synthetic_time=frozen_synthetic_time,
                        progress_callback=bundle_progress,
                    )
                    progress_placeholder.empty()
                    st.session_state["last_rolling_bundle_result"] = bundle_result
                    # 同时存储第一个文件的结果作为默认展示
                    first_success = next(
                        (cell for cell in bundle_result.cells if cell.result is not None),
                        None,
                    )
                    if first_success is not None:
                        st.session_state["last_rolling_result"] = first_success.result
                        st.session_state["rolling_bundle_selected_file"] = first_success.file_name
                    st.success(
                        f"滚动实验完成：{len(bundle_result.cells)} 个文件，"
                        f"成功 {sum(1 for c in bundle_result.cells if c.result is not None)} 个"
                    )
                except Exception as e:
                    progress_placeholder.empty()
                    st.error(f"滚动实验失败：{e}")
            else:
                # 单文件模式
                with st.spinner("滚动实验运行中..."):
                    try:
                        run_result = run_rolling_experiment(
                            cast(str, frozen_payload["data_source"]),
                            algorithms=algorithms,
                            date_column=frozen_date_column,
                            policy=frozen_policy,
                            synthetic_time=frozen_synthetic_time,
                        )
                        st.session_state["last_rolling_result"] = run_result
                        st.session_state.pop("last_rolling_bundle_result", None)
                        st.success(
                            f"滚动实验完成：experiment_id={run_result.experiment.experiment_id}，"
                            f"状态={run_result.experiment.status}"
                        )
                    except Exception as e:
                        st.error(f"滚动实验失败：{e}")

        # 展示任务状态
        display_bundle_result = cast(
            RollingBundleResult | None,
            st.session_state.get("last_rolling_bundle_result"),
        )
        display_task_result = cast(
            RollingExperimentResult | None,
            st.session_state.get("last_rolling_result"),
        )
        if display_bundle_result is not None:
            _render_rolling_bundle_task_summary(display_bundle_result)
        elif display_task_result is not None:
            _render_rolling_task_summary(display_task_result)

    with result_tab:
        st.subheader("实验结果查看")
        result_bundle = cast(
            RollingBundleResult | None,
            st.session_state.get("last_rolling_bundle_result"),
        )
        display_result = cast(
            RollingExperimentResult | None,
            st.session_state.get("last_rolling_result"),
        )
        partitions = cast(list[DayPartition], st.session_state.get("rolling_partitions", []))

        if result_bundle is not None:
            # 多文件模式：跨文件总览 + 单文件钻取
            _render_rolling_bundle_result(result_bundle, partitions, input_bundle)
        elif display_result is None:
            st.info("运行滚动实验后将在这里展示排行、active timeline 和 prediction ledger。")
            _render_rolling_history()
        else:
            _render_rolling_result(display_result, partitions, input_table)


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


def _render_rolling_bundle_task_summary(bundle_result: RollingBundleResult) -> None:
    """Render rolling bundle task summary showing per-file status."""
    st.subheader("多文件滚动实验状态")
    summary_cols = st.columns(4)
    success_count = sum(1 for c in bundle_result.cells if c.result is not None)
    summary_cols[0].metric("bundle_id", bundle_result.bundle_id)
    summary_cols[1].metric("文件总数", len(bundle_result.cells))
    summary_cols[2].metric("成功", success_count)
    summary_cols[3].metric("失败/部分失败", len(bundle_result.cells) - success_count)

    rows: list[dict[str, str]] = []
    for cell in bundle_result.cells:
        row: dict[str, str] = {
            "文件": cell.file_name,
            "状态": cell.status,
        }
        if cell.result is not None:
            row["cycles"] = str(len(cell.result.cycles))
            row["ledger rows"] = str(len(cell.result.ledger))
        else:
            row["cycles"] = "-"
            row["ledger rows"] = "-"
            row["错误信息"] = cell.error_message or ""
        rows.append(row)

    _render_filterable_dataframe(pd.DataFrame(rows), key=f"bundle_cells_{bundle_result.bundle_id}")


def _render_rolling_bundle_result(
    bundle_result: RollingBundleResult,
    partitions: list[DayPartition],
    input_bundle: DatasetBundle | None,
) -> None:
    """Render rolling bundle result with cross-file overview and per-file drill-down."""
    overview_tab, file_tab = st.tabs(["跨文件总览", "单文件钻取"])

    with overview_tab:
        _render_rolling_bundle_overview(bundle_result)

    with file_tab:
        _render_rolling_bundle_file_drilldown(bundle_result, partitions, input_bundle)


def _render_rolling_bundle_overview(bundle_result: RollingBundleResult) -> None:
    """Render cross-file overview: aggregated leaderboard and algorithm × file heatmap."""
    st.subheader("算法跨文件汇总")

    if not bundle_result.algorithm_metrics:
        st.warning("暂无聚合指标。")
    else:
        # Aggregated leaderboard
        rows = []
        for algo in bundle_result.algorithms:
            metrics = bundle_result.algorithm_metrics.get(algo.name, {})
            rows.append({
                "算法": algo.name,
                "Mean PA-F1": f"{metrics.get('mean_pa_f1', 0):.3f}",
                "Median PA-F1": f"{metrics.get('median_pa_f1', 0):.3f}",
                "Min PA-F1": f"{metrics.get('min_pa_f1', 0):.3f}",
                "Max PA-F1": f"{metrics.get('max_pa_f1', 0):.3f}",
                "文件成功率": f"{metrics.get('success_rate', 0):.0%}",
                "成功文件数": int(metrics.get("file_success_count", 0)),
            })
        _render_filterable_dataframe(
            pd.DataFrame(rows).sort_values("Mean PA-F1", ascending=False),
            key=f"bundle_leaderboard_{bundle_result.bundle_id}",
        )

    # Algorithm × File heatmap (files as rows, algorithms as columns)
    st.subheader("文件 × 算法 PA-F1 热力图")
    algo_names = [algo.name for algo in bundle_result.algorithms]
    heatmap_data = []
    for cell in bundle_result.cells:
        row_data: dict[str, Any] = {"文件": cell.file_name}
        for algo_name in algo_names:
            if cell.result is not None:
                matching = [r for r in cell.result.leaderboard if r.algorithm_name == algo_name]
                if matching:
                    row_data[algo_name] = matching[0].mean_pa_f1
                else:
                    row_data[algo_name] = None
            else:
                row_data[algo_name] = None
        heatmap_data.append(row_data)

    heatmap_df = pd.DataFrame(heatmap_data).set_index("文件")
    st.dataframe(
        heatmap_df.style.format("{:.3f}", na_rep="-").background_gradient(
            cmap="RdYlGn", axis=None, vmin=0, vmax=1
        ),
        width="stretch",
    )


def _render_rolling_bundle_file_drilldown(
    bundle_result: RollingBundleResult,
    partitions: list[DayPartition],
    input_bundle: DatasetBundle | None,
) -> None:
    """Render per-file drill-down with file selector."""
    success_cells = [cell for cell in bundle_result.cells if cell.result is not None]
    if not success_cells:
        st.warning("没有成功完成的文件结果。")
        return

    file_names = [cell.file_name for cell in success_cells]
    selected_file = st.selectbox(
        "选择文件查看详情",
        options=file_names,
        key="rolling_bundle_file_selector",
    )

    if selected_file is None:
        return

    selected_cell = next(
        (cell for cell in success_cells if cell.file_name == selected_file),
        None,
    )
    if selected_cell is None or selected_cell.result is None:
        st.warning(f"文件 {selected_file} 的结果不可用。")
        return

    # Get the corresponding input table for this file (if bundle available)
    file_input_table: Table | None = None
    if input_bundle is not None:
        for dataset_file in input_bundle.files:
            if dataset_file.name == selected_file:
                file_input_table = dataset_file.table
                break

    st.caption(f"文件：{selected_file}")
    _render_rolling_result(selected_cell.result, partitions, file_input_table)


def _render_rolling_detect_figure(
    cycles: list[RollingDayCycle],
    ledger_rows: list[Any],
    source_table: Table | None = None,
    detect_start_day: str | None = None,
) -> None:
    """Render concatenated Plotly time-series chart with training + detection periods."""
    import plotly.graph_objects as go

    valid = [c for c in cycles if c.detect_output is not None]
    if not valid:
        st.warning("该算法无可可视化的检测 cycle。")
        return

    # Use first valid cycle to determine metric column
    first_output = valid[0].detect_output
    assert first_output is not None
    metric_cols = [col for col in first_output.schema.columns_of(FieldRole.METRIC) if "." not in col]
    if not metric_cols:
        st.warning("检测输出中无指标列。")
        return
    metric = metric_cols[0]

    # ── 训练期数据 ──
    train_x: list[Any] = []
    train_y: list[float] = []
    train_true: list[int | None] = []
    if source_table is not None and metric in source_table.df.columns:
        src_df = source_table.df.copy()
        src_ts = source_table.timestamps()
        src_labels = source_table.labels()
        # 确定训练期行范围：detect_start_day 之前的数据
        if detect_start_day is not None:
            if src_ts is not None:
                try:
                    parsed_ts = pd.to_datetime(src_ts, utc=True, errors="coerce")
                    cutoff = pd.Timestamp(detect_start_day, tz="UTC")
                    train_mask = parsed_ts < cutoff
                    train_df = src_df.loc[train_mask]
                    train_ts = parsed_ts.loc[train_mask]
                    train_labels_series = src_labels.loc[train_mask] if src_labels is not None else None
                    for idx_pos, (_i, row) in enumerate(train_df.iterrows()):
                        train_x.append(train_ts.iloc[idx_pos] if train_ts is not None else idx_pos)
                        train_y.append(float(row[metric]))
                        train_true.append(
                            int(train_labels_series.iloc[idx_pos])
                            if train_labels_series is not None and not pd.isna(train_labels_series.iloc[idx_pos])
                            else None
                        )
                except Exception:
                    pass  # 解析失败则跳过训练期
            else:
                # 无 timestamp 列：用 detect_output 的合成 timestamp 反推训练期 x 轴
                first_detect_ts = first_output.timestamps()
                if first_detect_ts is not None and len(first_detect_ts) >= 2:
                    # 从 detect_output 推断合成 interval
                    ts0 = pd.Timestamp(first_detect_ts.iloc[0])
                    ts1 = pd.Timestamp(first_detect_ts.iloc[1])
                    interval = ts1 - ts0
                    # 训练行数 = 总行数 - 所有检测行数
                    total_detect_rows = sum(
                        len(c.detect_output.df) for c in valid if c.detect_output is not None
                    )
                    train_rows = max(0, len(src_df) - total_detect_rows)
                    # 训练期 timestamp = first_detect_ts 向前推 train_rows 个 interval
                    for i in range(train_rows):
                        train_x.append(ts0 - (train_rows - i) * interval)
                        train_y.append(float(src_df.iloc[i][metric]))
                        train_true.append(
                            int(src_labels.iloc[i])
                            if src_labels is not None and not pd.isna(src_labels.iloc[i])
                            else None
                        )
                else:
                    # 无合成 timestamp 可用，降级为整数 index
                    total_detect_rows = sum(
                        len(c.detect_output.df) for c in valid if c.detect_output is not None
                    )
                    train_rows = max(0, len(src_df) - total_detect_rows)
                    for i in range(train_rows):
                        train_x.append(i)
                        train_y.append(float(src_df.iloc[i][metric]))
                        train_true.append(
                            int(src_labels.iloc[i])
                            if src_labels is not None and not pd.isna(src_labels.iloc[i])
                            else None
                        )

    # ── 检测期数据 ──
    # Build positional lookup by iterating ledger per cutoff_day
    from collections import defaultdict
    ledger_by_day: dict[str, list[Any]] = defaultdict(list)
    for row in ledger_rows:
        ledger_by_day[str(row.cutoff_day)].append(row)

    detect_x: list[Any] = []
    detect_y: list[float] = []
    detect_upper: list[float | None] = []
    detect_lower: list[float | None] = []
    detect_pred: list[int] = []
    detect_true: list[int | None] = []
    detect_score: list[float | None] = []
    detect_day: list[str] = []

    for cycle in valid:
        output = cycle.detect_output
        assert output is not None
        day_str = str(cycle.cutoff_day)
        day_ledger = ledger_by_day.get(day_str, [])

        timestamps = output.timestamps()
        ts = timestamps.reset_index(drop=True) if timestamps is not None else pd.Series(range(len(output.df)))
        y = output.df[metric].reset_index(drop=True)
        pred = (
            output.df["predicted_label"].reset_index(drop=True).fillna(0).astype(int)
            if "predicted_label" in output.df.columns
            else pd.Series([0] * len(output.df))
        )

        upper_col = f"{metric}.threshold_upper"
        lower_col = f"{metric}.threshold_lower"
        score_col = f"{metric}.anomaly_score"
        upper = output.df[upper_col].reset_index(drop=True) if upper_col in output.df.columns else None
        lower = output.df[lower_col].reset_index(drop=True) if lower_col in output.df.columns else None
        score = output.df[score_col].reset_index(drop=True) if score_col in output.df.columns else None

        for i in range(len(output.df)):
            detect_x.append(ts.iloc[i])
            detect_y.append(float(y.iloc[i]))
            detect_upper.append(float(upper.iloc[i]) if upper is not None else None)
            detect_lower.append(float(lower.iloc[i]) if lower is not None else None)
            detect_pred.append(int(pred.iloc[i]))
            detect_score.append(float(score.iloc[i]) if score is not None else None)
            detect_day.append(day_str)
            if i < len(day_ledger):
                detect_true.append(day_ledger[i].label)
            else:
                detect_true.append(None)

    has_train = len(train_x) > 0
    has_timestamps = (
        (first_output.timestamps() is not None) if valid else False
    )

    fig = go.Figure()

    # ── 训练期渲染 ──
    if has_train:
        train_x_series = pd.Series(train_x)
        train_y_series = pd.Series(train_y)
        train_true_series = pd.Series(train_true, dtype="Int64")

        # 训练期背景带
        if train_x_series.iloc[0] is not None and train_x_series.iloc[-1] is not None:
            fig.add_vrect(
                x0=train_x_series.iloc[0],
                x1=train_x_series.iloc[-1],
                fillcolor="#e2e8f0",
                opacity=0.3,
                line_width=0,
                layer="below",
                annotation_text="训练期",
                annotation_position="top left",
            )

        # 训练期 GT 异常段
        if train_true_series.notna().any():
            from nextaiops_algo.pipeline.profile import anomaly_segments
            segments = anomaly_segments(train_true_series.fillna(0).astype(int).tolist())
            for start, end in segments:
                fig.add_vrect(
                    x0=train_x_series.iloc[start],
                    x1=train_x_series.iloc[end],
                    fillcolor="#64748b",
                    opacity=0.12,
                    line_width=0,
                    layer="below",
                )

        # 训练期指标线
        fig.add_trace(
            go.Scatter(
                x=train_x_series,
                y=train_y_series,
                mode="lines",
                name=f"{metric}（训练期）",
                line={"color": "#94a3b8", "width": 1.5},
                hovertemplate=(
                    "x=%{x}<br>value=%{y:.4g}<br>phase=训练<extra>训练期</extra>"
                ),
            )
        )

    # ── 检测期渲染 ──
    detect_x_series = pd.Series(detect_x)
    detect_y_series = pd.Series(detect_y)
    detect_pred_series = pd.Series(detect_pred)
    detect_true_series = pd.Series(detect_true, dtype="Int64")
    detect_day_series = pd.Series(detect_day)

    # 检测期 GT 异常段
    if detect_true_series.notna().any():
        from nextaiops_algo.pipeline.profile import anomaly_segments
        for _day_label, day_group in detect_day_series.groupby(detect_day_series):
            day_indices = day_group.index.tolist()
            day_true = detect_true_series.loc[day_indices]
            segments = anomaly_segments(day_true.fillna(0).astype(int).tolist())
            for start, end in segments:
                fig.add_vrect(
                    x0=detect_x_series.iloc[day_indices[start]],
                    x1=detect_x_series.iloc[day_indices[end]],
                    fillcolor="#64748b",
                    opacity=0.12,
                    line_width=0,
                    layer="below",
                )

    # 检测期指标线
    customdata = pd.DataFrame({
        "score": pd.Series(detect_score, dtype="float64"),
        "true": detect_true_series,
        "pred": detect_pred_series,
        "day": detect_day_series,
    })
    fig.add_trace(
        go.Scatter(
            x=detect_x_series,
            y=detect_y_series,
            mode="lines",
            name=metric,
            line={"color": "#2563eb", "width": 1.5},
            customdata=customdata,
            hovertemplate=(
                "x=%{x}<br>"
                "value=%{y:.4g}<br>"
                "score=%{customdata[0]:.4g}<br>"
                "true=%{customdata[1]}<br>"
                "pred=%{customdata[2]}<br>"
                "day=%{customdata[3]}"
                f"<extra>{metric}</extra>"
            ),
        )
    )

    # 阈值线
    upper_series = pd.Series(detect_upper, dtype="float64")
    lower_series = pd.Series(detect_lower, dtype="float64")
    if upper_series.notna().any():
        fig.add_trace(
            go.Scatter(
                x=detect_x_series,
                y=upper_series,
                mode="lines",
                name="上阈值",
                line={"color": "#059669", "dash": "dash", "width": 1},
                hovertemplate="x=%{x}<br>upper=%{y:.4g}<extra>上阈值</extra>",
            )
        )
    if lower_series.notna().any():
        fig.add_trace(
            go.Scatter(
                x=detect_x_series,
                y=lower_series,
                mode="lines",
                name="下阈值",
                line={"color": "#059669", "dash": "dash", "width": 1},
                hovertemplate="x=%{x}<br>lower=%{y:.4g}<extra>下阈值</extra>",
            )
        )

    # TP/FP/FN 标记
    if detect_true_series.notna().any():
        for label, mask, style in [
            ("TP", (detect_true_series == 1) & (detect_pred_series == 1), {"color": "#16a34a", "symbol": "circle", "size": 9}),
            ("FP", (detect_true_series == 0) & (detect_pred_series == 1), {"color": "#f97316", "symbol": "x", "size": 10}),
            ("FN", (detect_true_series == 1) & (detect_pred_series == 0), {"color": "#dc2626", "symbol": "diamond", "size": 9}),
        ]:
            if mask.any():
                fig.add_trace(
                    go.Scatter(
                        x=detect_x_series[mask],
                        y=detect_y_series[mask],
                        mode="markers",
                        name=label,
                        marker=style,
                        hovertemplate=(
                            "x=%{x}<br>value=%{y:.4g}<extra>" + label + "</extra>"
                        ),
                    )
                )
    else:
        pred_mask = detect_pred_series == 1
        if pred_mask.any():
            fig.add_trace(
                go.Scatter(
                    x=detect_x_series[pred_mask],
                    y=detect_y_series[pred_mask],
                    mode="markers",
                    name="检出异常",
                    marker={"color": "#dc2626", "size": 8, "symbol": "circle"},
                    hovertemplate="x=%{x}<br>value=%{y:.4g}<extra>检出</extra>",
                )
            )

    algo_name = valid[0].algorithm_name
    title_parts = [f"时序图：{algo_name}（{len(valid)} 个 cycle）"]
    if has_train:
        title_parts.append(f"训练 {len(train_x)} 行")
    fig.update_layout(
        title=" · ".join(title_parts),
        xaxis_title="Timestamp" if has_timestamps else "Index",
        yaxis_title=metric,
        template="plotly_white",
        height=500,
        hovermode="x unified",
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        margin={"l": 48, "r": 24, "t": 64, "b": 48},
    )
    fig.update_xaxes(
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="#64748b",
        spikethickness=1,
    )

    st.plotly_chart(fig, width="stretch", config=_plotly_config())


def _render_rolling_result(
    result: RollingExperimentResult,
    partitions: list[DayPartition],
    input_table: Table | None = None,
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

    leaderboard_tab, timeline_tab, detect_tab, exclusion_tab = st.tabs(
        ["算法排行", "Active Timeline", "检测时序图", "排除项汇总"]
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

    with detect_tab:
        # Algorithm selector: show all cycles for the selected algorithm concatenated
        completed_cycles = [
            c for c in result.cycles
            if c.status == "completed" and c.detect_output is not None
        ]
        if not completed_cycles:
            st.warning("暂无可可视化的检测 cycle。")
        else:
            # Group cycles by algorithm
            algo_cycles: dict[str, list[RollingDayCycle]] = {}
            for c in completed_cycles:
                algo_cycles.setdefault(c.algorithm_name, []).append(c)
            algo_names = sorted(algo_cycles.keys())

            selected_algo = st.selectbox(
                "选择算法",
                options=algo_names,
                key="rolling_detect_algo_selector",
            )
            if selected_algo is not None:
                selected_cycles = algo_cycles[selected_algo]

                # Aggregate metrics across all cycles for this algorithm
                all_metrics = [c.metrics for c in selected_cycles if c.metrics]
                if all_metrics:
                    mc = st.columns(7)
                    mc[0].metric("Cycles", len(selected_cycles))
                    for i, key in enumerate(["precision", "recall", "f1", "pa_f1", "seg_recall", "seg_precision"]):
                        values = [m[key] for m in all_metrics if key in m]
                        avg = sum(values) / len(values) if values else 0.0
                        mc[i + 1].metric(
                            {
                                "precision": "Precision",
                                "recall": "Recall",
                                "f1": "F1",
                                "pa_f1": "PA-F1",
                                "seg_recall": "段召回率",
                                "seg_precision": "段精确率",
                            }[key],
                            f"{avg:.3f}",
                            help={
                                "precision": "检出的异常中有多少是真的（点级）",
                                "recall": "真实异常中有多少被检出（点级）",
                                "f1": "Precision 与 Recall 的调和平均（点级）",
                                "pa_f1": "按异常段调整后的 F1，命中段内任意一点即视为全段命中",
                                "seg_recall": f"真实异常段中被检测出的比例（IoU≥{result.experiment.policy.segment_iou_threshold}）",
                                "seg_precision": f"检测出的异常段中有多少是正确的（IoU≥{result.experiment.policy.segment_iou_threshold}）",
                            }[key],
                        )

                    # 段级统计
                    from nextaiops_algo.pipeline.profile import anomaly_segments
                    total_true_segs = 0
                    total_pred_segs = 0
                    for c in selected_cycles:
                        if c.detect_output is not None:
                            out_df = c.detect_output.df
                            if "predicted_label" in out_df.columns:
                                pred_labels = out_df["predicted_label"].fillna(0).astype(int).tolist()
                                total_pred_segs += len(anomaly_segments(pred_labels))
                    # 从 ledger 统计真实段数
                    algo_ledger_for_segs = [row for row in result.ledger if row.algorithm_name == selected_algo]
                    # Group by cutoff_day to get per-cycle true segments
                    from collections import defaultdict
                    ledger_by_day_segs: dict[str, list[int | None]] = defaultdict(list)
                    for row in algo_ledger_for_segs:
                        ledger_by_day_segs[str(row.cutoff_day)].append(row.label)
                    for day_labels in ledger_by_day_segs.values():
                        true_labels = [int(v) if v is not None else 0 for v in day_labels]
                        total_true_segs += len(anomaly_segments(true_labels))

                    iou_thresh = result.experiment.policy.segment_iou_threshold
                    seg_info_cols = st.columns(3)
                    seg_info_cols[0].metric(
                        "真实异常段数",
                        total_true_segs,
                        help="所有检测周期内的真实异常连续段总数",
                    )
                    seg_info_cols[1].metric(
                        "检测出异常段数",
                        total_pred_segs,
                        help="算法检出的异常连续段总数",
                    )
                    seg_recall_avg = (
                        sum(m.get("seg_recall", 0) for m in all_metrics) / len(all_metrics)
                        if all_metrics
                        else 0.0
                    )
                    seg_precision_avg = (
                        sum(m.get("seg_precision", 0) for m in all_metrics) / len(all_metrics)
                        if all_metrics
                        else 0.0
                    )
                    seg_info_cols[2].metric(
                        f"段匹配阈值 (IoU≥{iou_thresh:.0%})",
                        f"{seg_recall_avg:.0%} / {seg_precision_avg:.0%}",
                        help=f"段召回率（真实段被检出比例）/ 段精确率（检测段正确比例），IoU≥{iou_thresh} 视为有效匹配",
                    )

                # Filter ledger rows for this algorithm
                algo_ledger = [row for row in result.ledger if row.algorithm_name == selected_algo]
                _render_rolling_detect_figure(
                    selected_cycles,
                    algo_ledger,
                    source_table=input_table,
                    detect_start_day=result.experiment.policy.detect_start_day.isoformat()
                    if result.experiment.policy.detect_start_day is not None
                    else None,
                )

        # Ledger as expandable raw data
        ledger_df = _build_ledger_dataframe(result)
        if not ledger_df.empty:
            with st.expander("Prediction Ledger（原始推理记录，用于审计与调试）"):
                st.caption(
                    "Prediction Ledger 记录每条推理的 timestamp、算法、active_model_id、"
                    "predicted_label、score 与 ground truth label。仅展示前 200 行。"
                )
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
    """Render persisted rolling experiment history with pagination."""
    store = SqliteTrackingStore()
    total_count = store.count_rolling_experiments()
    if total_count == 0:
        st.info("暂无历史滚动实验记录。")
        return

    page_size = 10
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    current_page = int(st.session_state.get("rolling_history_page", 1))
    if current_page > total_pages:
        current_page = total_pages

    st.subheader(f"历史滚动实验（共 {total_count} 条）")
    page_cols = st.columns([1, 3, 1])
    with page_cols[0]:
        if st.button("◀ 上一页", disabled=current_page <= 1, key="rolling_history_prev"):
            st.session_state["rolling_history_page"] = current_page - 1
            st.rerun()
    with page_cols[1]:
        st.caption(f"第 {current_page} / {total_pages} 页")
    with page_cols[2]:
        if st.button("下一页 ▶", disabled=current_page >= total_pages, key="rolling_history_next"):
            st.session_state["rolling_history_page"] = current_page + 1
            st.rerun()

    offset = (current_page - 1) * page_size
    experiments = store.list_rolling_experiments(limit=page_size, offset=offset)
    if not experiments:
        st.info("当前页无记录。")
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
    _render_filterable_dataframe(
        pd.DataFrame(history_rows),
        key=f"rolling_history_p{current_page}",
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
