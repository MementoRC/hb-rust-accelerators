"""Guard: under RUST_ACCELERATORS_FORCE_FALLBACK=1 the pure-Python fallback must be in use."""

from __future__ import annotations

import os

import pytest
import rust_accelerators
import rust_accelerators._pure_order_expiration_entry as pure_oee
import rust_accelerators.metrics
import rust_accelerators.order_expiration_entry

pytestmark = pytest.mark.skipif(
    os.environ.get("RUST_ACCELERATORS_FORCE_FALLBACK") != "1",
    reason="RUST_ACCELERATORS_FORCE_FALLBACK is not set",
)


def test_metrics_uses_fallback() -> None:
    assert rust_accelerators.metrics._ACCELERATED is False


def test_order_expiration_entry_uses_fallback() -> None:
    assert rust_accelerators.order_expiration_entry._ACCELERATED is False


def test_order_expiration_entry_is_pure_class() -> None:
    cls = rust_accelerators.order_expiration_entry.OrderExpirationEntry
    assert cls is pure_oee.OrderExpirationEntry


def test_package_is_not_accelerated() -> None:
    assert rust_accelerators.is_accelerated() is False
