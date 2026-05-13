"""Algorithm parameter metadata and normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ParamType = Literal["float", "int", "str", "bool", "enum"]


@dataclass(frozen=True)
class AlgorithmParamSpec:
    """Metadata for one user-configurable algorithm parameter.

    Attributes:
        name: Parameter name accepted by the algorithm constructor.
        type: UI/control type and normalization hint.
        default: Default value used when the user does not override it.
        description: Human-readable explanation shown in UI.
        min_value: Optional minimum value for numeric parameters.
        max_value: Optional maximum value for numeric parameters.
        choices: Optional allowed values for enum parameters.
        affects_run_identity: Whether this parameter is part of experiment identity.
    """

    name: str
    type: ParamType
    default: object
    description: str
    min_value: float | None = None
    max_value: float | None = None
    choices: tuple[object, ...] = ()
    affects_run_identity: bool = True


def normalize_params(
    specs: tuple[AlgorithmParamSpec, ...],
    raw_params: dict[str, object] | None,
) -> dict[str, object]:
    """Normalize raw params according to specs, filling defaults.

    Args:
        specs: Parameter specs declared by an algorithm.
        raw_params: User supplied parameter values.

    Returns:
        Dict containing every declared parameter with normalized values.

    Raises:
        ValueError: If a value cannot be converted or violates spec constraints.
    """
    raw = raw_params or {}
    normalized: dict[str, object] = {}

    for spec in specs:
        value = raw.get(spec.name, spec.default)
        normalized[spec.name] = _normalize_value(spec, value)

    unknown = sorted(set(raw) - {spec.name for spec in specs})
    if unknown:
        raise ValueError(f"Unknown algorithm parameter(s): {', '.join(unknown)}")

    return normalized


def identity_params(
    specs: tuple[AlgorithmParamSpec, ...],
    params: dict[str, object],
) -> dict[str, object]:
    """Filter normalized params to values that affect run identity."""
    identity_names = {spec.name for spec in specs if spec.affects_run_identity}
    return {key: params[key] for key in sorted(identity_names) if key in params}


def format_experiment_label(algorithm_name: str, params: dict[str, object]) -> str:
    """Build a readable experiment label from algorithm name and params."""
    if not params:
        return algorithm_name

    parts = [f"{key}={params[key]}" for key in sorted(params)]
    return f"{algorithm_name}[{', '.join(parts)}]"


def _normalize_value(spec: AlgorithmParamSpec, value: object) -> object:
    """Normalize one value according to its spec."""
    if spec.type == "float":
        normalized: object = _to_float(value)
    elif spec.type == "int":
        normalized = _to_int(value)
    elif spec.type == "str":
        normalized = str(value)
    elif spec.type == "bool":
        normalized = _to_bool(value)
    elif spec.type == "enum":
        normalized = value
        if spec.choices and normalized not in spec.choices:
            allowed = ", ".join(str(choice) for choice in spec.choices)
            raise ValueError(f"Parameter '{spec.name}' must be one of: {allowed}")
    else:
        normalized = value

    if isinstance(normalized, (float, int)) and not isinstance(normalized, bool):
        numeric_value = float(normalized)
        if spec.min_value is not None and numeric_value < spec.min_value:
            raise ValueError(f"Parameter '{spec.name}' must be >= {spec.min_value}")
        if spec.max_value is not None and numeric_value > spec.max_value:
            raise ValueError(f"Parameter '{spec.name}' must be <= {spec.max_value}")

    return normalized


def _to_bool(value: object) -> bool:
    """Convert common bool-like values to bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    raise ValueError(f"Cannot convert {value!r} to bool")


def _to_float(value: object) -> float:
    """Convert a scalar value to float."""
    if isinstance(value, bool):
        raise ValueError(f"Cannot convert {value!r} to float")
    if isinstance(value, (str, int, float)):
        return float(value)
    raise ValueError(f"Cannot convert {value!r} to float")


def _to_int(value: object) -> int:
    """Convert a scalar value to int."""
    if isinstance(value, bool):
        raise ValueError(f"Cannot convert {value!r} to int")
    if isinstance(value, (str, int, float)):
        return int(value)
    raise ValueError(f"Cannot convert {value!r} to int")
