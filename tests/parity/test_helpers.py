"""Smoke tests for the parity helpers in conftest.py."""

from __future__ import annotations

import types

import numpy as np
import pytest

from tests.parity.helpers import (
    STANDARD_SIZES,
    assert_numeric_parity,
    assert_object_parity,
    generate_numeric_data,
)

pytestmark = pytest.mark.parity


def test_numeric_parity_passes_and_fails() -> None:
    assert_numeric_parity(lambda x: (x, 1.0), lambda x: (x, 1.0 + 1e-12), 2.0)
    with pytest.raises(AssertionError):
        assert_numeric_parity(lambda x: x, lambda x: x + 1.0, 2.0)


def test_object_parity_passes_and_fails() -> None:
    a = types.SimpleNamespace(name="x", value=1.0)
    b = types.SimpleNamespace(name="x", value=1.0)
    assert_object_parity(a, b, ("name", "value"))
    b.name = "y"
    with pytest.raises(AssertionError):
        assert_object_parity(a, b, ("name",))


def test_generate_numeric_data_is_deterministic() -> None:
    np.testing.assert_array_equal(generate_numeric_data(10), generate_numeric_data(10))


def test_pnl_series_fixture(pnl_series: np.ndarray) -> None:
    assert pnl_series.ndim == 1
    assert len(pnl_series) in STANDARD_SIZES


def test_returns_series_fixture(returns_series: np.ndarray) -> None:
    assert len(returns_series) in STANDARD_SIZES


def test_pnl_values_fixture(pnl_values: np.ndarray) -> None:
    assert len(pnl_values) in STANDARD_SIZES


def test_rust_core_fixture(rust_core: types.ModuleType) -> None:
    assert hasattr(rust_core.order_expiration_entry, "OrderExpirationEntry")


def test_python_metrics_fixture_forces_fallback(python_metrics: types.ModuleType) -> None:
    assert python_metrics.is_accelerated() is False
