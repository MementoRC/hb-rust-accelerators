"""Benchmark tests for performance metrics: Rust vs Python fallback."""

from __future__ import annotations

import numpy as np
import pytest
from rust_accelerators.metrics import (
    _ACCELERATED,
    calculate_all_metrics,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe_ratio,
)


def _generate_pnl_series(n: int, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.001, 0.02, n)
    return np.cumsum(returns)


def _generate_returns(n: int, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0.001, 0.02, n)


def _generate_pnl_values(n: int, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0.5, 10.0, n)


# --- Data size fixtures ---

SIZES = [100, 1_000, 10_000, 100_000]


@pytest.fixture(params=SIZES, ids=[f"n={s}" for s in SIZES])
def pnl_series(request):
    return _generate_pnl_series(request.param)


@pytest.fixture(params=SIZES, ids=[f"n={s}" for s in SIZES])
def returns_series(request):
    return _generate_returns(request.param)


@pytest.fixture(params=SIZES, ids=[f"n={s}" for s in SIZES])
def pnl_values(request):
    return _generate_pnl_values(request.param)


# --- Benchmark tests ---


@pytest.mark.benchmark(group="max_drawdown")
def test_max_drawdown(benchmark, pnl_series):
    benchmark(calculate_max_drawdown, pnl_series)


@pytest.mark.benchmark(group="sharpe_ratio")
def test_sharpe_ratio(benchmark, returns_series):
    benchmark(calculate_sharpe_ratio, returns_series)


@pytest.mark.benchmark(group="profit_factor")
def test_profit_factor(benchmark, pnl_values):
    benchmark(calculate_profit_factor, pnl_values)


@pytest.mark.benchmark(group="all_metrics")
def test_all_metrics(benchmark, pnl_series):
    benchmark(calculate_all_metrics, pnl_series)


def test_acceleration_status():
    """Report whether benchmarks ran with Rust acceleration or Python fallback."""
    status = "Rust" if _ACCELERATED else "Python fallback"
    pytest.skip(f"Acceleration status: {status} (informational)")
