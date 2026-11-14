"""Metrics parity tests -- Rust (_core) vs the pure-Python fallback.

Reference template for numeric-function parity tests: each test calls both
implementations with identical inputs and asserts approximate equality. The Rust
side comes from the ``rust_core`` fixture, the Python side from ``python_metrics``
(which forces the wrapper onto its pure-Python path).
"""

from __future__ import annotations

import types

import numpy as np
import pytest

from tests.parity.helpers import assert_numeric_parity

EMPTY = np.array([], dtype=np.float64)


@pytest.mark.parity
class TestMaxDrawdownParity:
    @pytest.fixture(autouse=True)
    def _impls(self, rust_core: types.ModuleType, python_metrics: types.ModuleType) -> None:
        self.rs = rust_core.calculate_max_drawdown
        self.py = python_metrics.calculate_max_drawdown

    def test_standard_data(self, pnl_series: np.ndarray) -> None:
        assert_numeric_parity(self.rs, self.py, pnl_series)

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(EMPTY, id="empty"),
            pytest.param(np.array([42.0]), id="single"),
            pytest.param(np.array([1.0, 2.0, 3.0, 4.0, 5.0]), id="increasing"),
            pytest.param(np.array([1.0, 1.0, 1.0, 1.0]), id="constant"),
            pytest.param(np.array([1e15, 2e15, 1.5e15, 1.8e15]), id="large"),
            pytest.param(np.array([1e-15, 2e-15, 1.5e-15, 1.8e-15]), id="small"),
        ],
    )
    def test_edge_cases(self, data: np.ndarray) -> None:
        assert_numeric_parity(self.rs, self.py, data)


@pytest.mark.parity
class TestSharpeRatioParity:
    @pytest.fixture(autouse=True)
    def _impls(self, rust_core: types.ModuleType, python_metrics: types.ModuleType) -> None:
        self.rs = rust_core.calculate_sharpe_ratio
        self.py = python_metrics.calculate_sharpe_ratio

    def test_standard_data(self, returns_series: np.ndarray) -> None:
        assert_numeric_parity(self.rs, self.py, returns_series)

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(EMPTY, id="empty"),
            pytest.param(np.array([42.0]), id="single"),
            pytest.param(np.array([1.0, 1.0, 1.0, 1.0]), id="zero-variance"),
        ],
    )
    def test_edge_cases(self, data: np.ndarray) -> None:
        assert_numeric_parity(self.rs, self.py, data)

    def test_custom_periods(self) -> None:
        data = np.array([0.01, -0.02, 0.015, -0.005, 0.03])
        assert_numeric_parity(self.rs, self.py, data, 12)


@pytest.mark.parity
class TestProfitFactorParity:
    @pytest.fixture(autouse=True)
    def _impls(self, rust_core: types.ModuleType, python_metrics: types.ModuleType) -> None:
        self.rs = rust_core.calculate_profit_factor
        self.py = python_metrics.calculate_profit_factor

    def test_standard_data(self, pnl_values: np.ndarray) -> None:
        assert_numeric_parity(self.rs, self.py, pnl_values)

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(EMPTY, id="empty"),
            pytest.param(np.array([1.0, 2.0, 3.0]), id="all-positive"),
            pytest.param(np.array([-1.0, -2.0, -3.0]), id="all-negative"),
            pytest.param(np.array([1e15, -2e15, 1.5e15]), id="large"),
        ],
    )
    def test_edge_cases(self, data: np.ndarray) -> None:
        assert_numeric_parity(self.rs, self.py, data)


@pytest.mark.parity
class TestAllMetricsParity:
    @pytest.fixture(autouse=True)
    def _impls(self, rust_core: types.ModuleType, python_metrics: types.ModuleType) -> None:
        self.rs = rust_core.calculate_all_metrics
        self.py = python_metrics.calculate_all_metrics

    def test_standard_data(self, pnl_series: np.ndarray) -> None:
        assert_numeric_parity(self.rs, self.py, pnl_series)

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(EMPTY, id="empty"),
            pytest.param(np.array([42.0]), id="single"),
        ],
    )
    def test_edge_cases(self, data: np.ndarray) -> None:
        assert_numeric_parity(self.rs, self.py, data)

    def test_custom_periods(self) -> None:
        data = np.array([50.0, 100.0, 80.0, 90.0, 95.0])
        assert_numeric_parity(self.rs, self.py, data, 12)
