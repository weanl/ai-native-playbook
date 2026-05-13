"""Unit tests for algorithm parameter metadata helpers."""

import pytest

from nextaiops_algo.algorithms.params import (
    AlgorithmParamSpec,
    format_experiment_label,
    identity_params,
    normalize_params,
)


def test_normalize_params_fills_defaults_and_casts_values() -> None:
    """normalize_params() fills defaults and casts according to specs."""
    specs = (
        AlgorithmParamSpec(
            name="k",
            type="float",
            default=3.0,
            description="threshold multiplier",
            min_value=0.1,
        ),
        AlgorithmParamSpec(
            name="enabled",
            type="bool",
            default=True,
            description="toggle",
        ),
    )

    params = normalize_params(specs, {"k": "2.5", "enabled": "false"})

    assert params == {"k": 2.5, "enabled": False}


def test_normalize_params_rejects_unknown_param() -> None:
    """Unknown params are rejected for algorithms that declare specs."""
    specs = (AlgorithmParamSpec(name="k", type="float", default=3.0, description="threshold"),)

    with pytest.raises(ValueError, match="Unknown algorithm parameter"):
        normalize_params(specs, {"unknown": 1})


def test_normalize_params_checks_numeric_bounds() -> None:
    """Numeric min/max bounds are enforced."""
    specs = (
        AlgorithmParamSpec(
            name="k",
            type="float",
            default=3.0,
            description="threshold",
            min_value=0.1,
        ),
    )

    with pytest.raises(ValueError, match="must be >="):
        normalize_params(specs, {"k": 0.0})


def test_identity_params_filters_non_identity_values() -> None:
    """identity_params() keeps only specs marked as identity-affecting."""
    specs = (
        AlgorithmParamSpec(name="k", type="float", default=3.0, description="threshold"),
        AlgorithmParamSpec(
            name="notes",
            type="str",
            default="",
            description="free-form notes",
            affects_run_identity=False,
        ),
    )

    params = identity_params(specs, {"k": 3.0, "notes": "demo"})

    assert params == {"k": 3.0}


def test_format_experiment_label() -> None:
    """format_experiment_label() returns a stable readable label."""
    assert format_experiment_label("three_sigma", {"k": 3.0}) == "three_sigma[k=3.0]"
    assert format_experiment_label("three_sigma", {}) == "three_sigma"
