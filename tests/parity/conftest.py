"""Reusable parity test fixtures.

Parity tests need the compiled ``rust_accelerators._core`` extension: they are skipped when it is
missing, or failed when ``RUST_ACCELERATORS_REQUIRE_RUST=1`` (same convention as
``tests/unit/test_acceleration.py``).
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import types
from collections.abc import Iterator

import numpy as np
import pytest
import rust_accelerators.metrics as metrics_module

from tests.parity.helpers import STANDARD_SIZES, generate_numeric_data

try:
    _core_available = importlib.util.find_spec("rust_accelerators._core") is not None
except ImportError:
    _core_available = False

_require_rust = os.environ.get("RUST_ACCELERATORS_REQUIRE_RUST") == "1"


# --- Rust gate and module access ---


@pytest.fixture(autouse=True)
def _require_rust_core() -> None:
    """Skip (or fail under RUST_ACCELERATORS_REQUIRE_RUST=1) when _core is missing."""
    if _core_available:
        return
    if _require_rust:
        pytest.fail(
            "RUST_ACCELERATORS_REQUIRE_RUST=1 but rust_accelerators._core is not "
            "importable (extension not built?)"
        )
    pytest.skip("rust_accelerators._core extension is not built")


@pytest.fixture
def rust_core() -> types.ModuleType:
    """The compiled ``rust_accelerators._core`` module.

    ``_core`` is not a package: reach submodules by attribute access, e.g.
    ``rust_core.order_expiration_entry.OrderExpirationEntry``.
    """
    return importlib.import_module("rust_accelerators._core")


@pytest.fixture
def python_metrics(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.ModuleType]:
    """``rust_accelerators.metrics`` forced onto its inline pure-Python fallback."""
    monkeypatch.setattr(metrics_module, "_ACCELERATED", False)
    yield metrics_module


# --- Standard data fixtures (parametrized by size) ---


@pytest.fixture(params=STANDARD_SIZES, ids=[f"n={s}" for s in STANDARD_SIZES])
def pnl_series(request: pytest.FixtureRequest) -> np.ndarray:
    """Cumulative P&L series for drawdown/all-metrics tests."""
    return np.cumsum(generate_numeric_data(request.param))


@pytest.fixture(params=STANDARD_SIZES, ids=[f"n={s}" for s in STANDARD_SIZES])
def returns_series(request: pytest.FixtureRequest) -> np.ndarray:
    """Returns series for Sharpe ratio tests."""
    return generate_numeric_data(request.param)


@pytest.fixture(params=STANDARD_SIZES, ids=[f"n={s}" for s in STANDARD_SIZES])
def pnl_values(request: pytest.FixtureRequest) -> np.ndarray:
    """Individual trade P&L values for profit factor tests."""
    rng = np.random.default_rng(42)
    return rng.normal(0.5, 10.0, request.param)
