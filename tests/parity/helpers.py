"""Assertion and data helpers for Rust vs Python parity tests.

Plain functions imported directly by parity tests. Pytest fixtures live in
``tests/parity/conftest.py``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import pytest

__all__ = [
    "STANDARD_SIZES",
    "assert_numeric_parity",
    "assert_object_parity",
    "generate_numeric_data",
]

STANDARD_SIZES = [100, 1_000, 10_000]


def assert_numeric_parity(
    rust_fn: Callable[..., Any],
    py_fn: Callable[..., Any],
    *args: Any,
    rel: float = 1e-9,
) -> None:
    """Call both functions with identical args and assert the results match.

    Handles scalar and tuple returns via ``pytest.approx``.
    """
    rust_result = rust_fn(*args)
    py_result = py_fn(*args)
    assert rust_result == pytest.approx(py_result, rel=rel), (
        f"Parity failure:\n  Rust: {rust_result}\n  Python: {py_result}"
    )


def assert_object_parity(rust_obj: object, py_obj: object, fields: Sequence[str]) -> None:
    """Field-by-field comparison for class-based module parity.

    Float fields are compared with ``pytest.approx``; everything else exactly.
    """
    for field in fields:
        rust_val = getattr(rust_obj, field)
        py_val = getattr(py_obj, field)
        if isinstance(rust_val, float) or isinstance(py_val, float):
            assert rust_val == pytest.approx(py_val), (
                f"Parity failure on field '{field}':\n  Rust: {rust_val}\n  Python: {py_val}"
            )
        else:
            assert rust_val == py_val, (
                f"Parity failure on field '{field}':\n  Rust: {rust_val}\n  Python: {py_val}"
            )


def generate_numeric_data(n: int, seed: int = 42, dtype: type = np.float64) -> np.ndarray:
    """Deterministic numpy array for reproducible parity tests."""
    rng = np.random.default_rng(seed)
    return rng.normal(0.001, 0.02, n).astype(dtype)
