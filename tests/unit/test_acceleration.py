"""Regression: accelerated modules must actually use the Rust backend when built."""

from __future__ import annotations

import importlib.util

import pytest
import rust_accelerators
from rust_accelerators import metrics, order_expiration_entry

try:
    _core_available = importlib.util.find_spec("rust_accelerators._core") is not None
except ImportError:
    _core_available = False

pytestmark = pytest.mark.skipif(
    not _core_available,
    reason="rust_accelerators._core extension is not built",
)


def test_package_is_accelerated() -> None:
    assert rust_accelerators.is_accelerated() is True


def test_metrics_is_accelerated() -> None:
    assert metrics.is_accelerated() is True


def test_order_expiration_entry_is_accelerated() -> None:
    assert order_expiration_entry.is_accelerated() is True


def test_order_expiration_entry_is_rust_class() -> None:
    from rust_accelerators import _core

    cls = order_expiration_entry.OrderExpirationEntry
    assert cls is _core.order_expiration_entry.OrderExpirationEntry
    assert cls.__module__ != "rust_accelerators.order_expiration_entry"
