"""Tests for the order_expiration_entry migration.

Covers the pure-Python fallback (always available) and, when the Rust
extension is importable, the accelerated variant under the same API.

Test cases are written from scratch (no pre-existing hummingbot test suite
for this module) but derived from:
  - The C++ operator< semantics in OrderExpirationEntry.cpp
  - The Cython property API in order_expiration_entry.pyx
  - paper_trade_exchange usage (sorted sets, attribute access)
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from typing import Any

import pytest

# Import from the permanent package location.
from rust_accelerators.order_expiration_entry import (
    OrderExpirationEntry,
    is_accelerated,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def entry() -> OrderExpirationEntry:
    return OrderExpirationEntry(
        trading_pair="BTC-USDT",
        order_id="order-001",
        timestamp=1_700_000_000.0,
        expiration_ts=1_700_000_060.0,
    )


@pytest.fixture()
def entry_same_expiry_later_id() -> OrderExpirationEntry:
    """Same expiration_timestamp, lexicographically later order_id."""
    return OrderExpirationEntry(
        trading_pair="ETH-USDT",
        order_id="order-999",
        timestamp=1_700_000_001.0,
        expiration_ts=1_700_000_060.0,
    )


@pytest.fixture()
def entry_later_expiry() -> OrderExpirationEntry:
    return OrderExpirationEntry(
        trading_pair="BTC-USDT",
        order_id="order-002",
        timestamp=1_700_000_000.0,
        expiration_ts=1_700_000_120.0,
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_basic_construction(self, entry: OrderExpirationEntry) -> None:
        assert entry.trading_pair == "BTC-USDT"
        assert entry.order_id == "order-001"
        assert entry.timestamp == pytest.approx(1_700_000_000.0)
        assert entry.expiration_timestamp == pytest.approx(1_700_000_060.0)

    def test_default_values_from_cpp_default_ctor(self) -> None:
        """Equivalent to C++ OrderExpirationEntry() default constructor."""
        e = OrderExpirationEntry("", "", 0.0, 0.0)
        assert e.trading_pair == ""
        assert e.order_id == ""
        assert e.timestamp == 0.0
        assert e.expiration_timestamp == 0.0

    def test_int_timestamps_coerced_to_float(self) -> None:
        e = OrderExpirationEntry("BTC-USDT", "x", 1000, 2000)
        assert isinstance(e.timestamp, float)
        assert isinstance(e.expiration_timestamp, float)

    def test_unicode_trading_pair(self) -> None:
        e = OrderExpirationEntry("BTC-USDT", "ord-1", 1.0, 2.0)
        assert e.trading_pair == "BTC-USDT"

    def test_empty_order_id(self) -> None:
        e = OrderExpirationEntry("BTC-USDT", "", 1.0, 2.0)
        assert e.order_id == ""


# ---------------------------------------------------------------------------
# Properties (read-only)
# ---------------------------------------------------------------------------


class TestProperties:
    def test_trading_pair_is_readonly(self, entry: OrderExpirationEntry) -> None:
        with pytest.raises(AttributeError):
            entry.trading_pair = "ETH-USDT"  # type: ignore[misc]

    def test_order_id_is_readonly(self, entry: OrderExpirationEntry) -> None:
        with pytest.raises(AttributeError):
            entry.order_id = "other"  # type: ignore[misc]

    def test_timestamp_is_readonly(self, entry: OrderExpirationEntry) -> None:
        with pytest.raises(AttributeError):
            entry.timestamp = 0.0  # type: ignore[misc]

    def test_expiration_timestamp_is_readonly(self, entry: OrderExpirationEntry) -> None:
        with pytest.raises(AttributeError):
            entry.expiration_timestamp = 0.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------


class TestRepr:
    def test_repr_format(self, entry: OrderExpirationEntry) -> None:
        r = repr(entry)
        assert r.startswith("OrderExpirationEntry(")
        assert "BTC-USDT" in r
        assert "order-001" in r
        assert "1700000000.0" in r
        assert "1700000060.0" in r

    def test_repr_empty_entry(self) -> None:
        e = OrderExpirationEntry("", "", 0.0, 0.0)
        assert repr(e) == "OrderExpirationEntry('', '', 0.0, '0.0')"


# ---------------------------------------------------------------------------
# Ordering — C++ operator< semantics
# ---------------------------------------------------------------------------


LO_HI_CASES = [
    (operator.lt, True),
    (operator.le, True),
    (operator.gt, False),
    (operator.ge, False),
]
HI_LO_CASES = [
    (operator.lt, False),
    (operator.le, False),
    (operator.gt, True),
    (operator.ge, True),
]
EQUAL_CASES = [
    (operator.lt, False),
    (operator.le, True),
    (operator.gt, False),
    (operator.ge, True),
]
ALL_OPS = [operator.lt, operator.le, operator.gt, operator.ge]


@pytest.fixture(params=["later_expiry", "same_expiry_later_id"])
def ordered_pair(
    request: pytest.FixtureRequest,
    entry: OrderExpirationEntry,
) -> tuple[OrderExpirationEntry, OrderExpirationEntry]:
    """(lower, higher) pair. Primary key: expiration ascending; secondary: order_id."""
    higher: OrderExpirationEntry = request.getfixturevalue(
        {
            "later_expiry": "entry_later_expiry",
            "same_expiry_later_id": "entry_same_expiry_later_id",
        }[request.param]
    )
    return entry, higher


@pytest.fixture()
def entry_clone(entry: OrderExpirationEntry) -> OrderExpirationEntry:
    return OrderExpirationEntry(
        entry.trading_pair,
        entry.order_id,
        entry.timestamp,
        entry.expiration_timestamp,
    )


class TestOrdering:
    @pytest.mark.parametrize(("op", "expected"), LO_HI_CASES)
    def test_lower_vs_higher(
        self,
        ordered_pair: tuple[OrderExpirationEntry, OrderExpirationEntry],
        op: Callable[[Any, Any], bool],
        expected: bool,
    ) -> None:
        lower, higher = ordered_pair
        assert op(lower, higher) is expected

    @pytest.mark.parametrize(("op", "expected"), HI_LO_CASES)
    def test_higher_vs_lower(
        self,
        ordered_pair: tuple[OrderExpirationEntry, OrderExpirationEntry],
        op: Callable[[Any, Any], bool],
        expected: bool,
    ) -> None:
        lower, higher = ordered_pair
        assert op(higher, lower) is expected

    @pytest.mark.parametrize(("op", "expected"), EQUAL_CASES)
    def test_equal_entries(
        self,
        entry: OrderExpirationEntry,
        entry_clone: OrderExpirationEntry,
        op: Callable[[Any, Any], bool],
        expected: bool,
    ) -> None:
        assert op(entry, entry_clone) is expected

    def test_sorted_pair(
        self,
        ordered_pair: tuple[OrderExpirationEntry, OrderExpirationEntry],
    ) -> None:
        """sorted() places the lower entry first regardless of input order."""
        lower, higher = ordered_pair
        assert sorted([higher, lower]) == [lower, higher]

    def test_max_pair(
        self,
        ordered_pair: tuple[OrderExpirationEntry, OrderExpirationEntry],
    ) -> None:
        lower, higher = ordered_pair
        assert max(lower, higher) is higher

    @pytest.mark.parametrize("op", ALL_OPS)
    def test_ordering_non_entry_unsupported(
        self,
        entry: OrderExpirationEntry,
        op: Callable[[Any, Any], bool],
    ) -> None:
        with pytest.raises(TypeError):
            op(entry, 42)

    def test_sort_by_expiry_then_order_id(self) -> None:
        """sorted() should respect C++ operator< ordering."""
        e1 = OrderExpirationEntry("X", "b", 1.0, 200.0)
        e2 = OrderExpirationEntry("X", "a", 1.0, 100.0)
        e3 = OrderExpirationEntry("X", "c", 1.0, 200.0)
        result = sorted([e1, e2, e3])
        assert result[0].expiration_timestamp == pytest.approx(100.0)
        assert result[1].order_id == "b"
        assert result[2].order_id == "c"

    def test_usable_in_sorted_set_pattern(self) -> None:
        """paper_trade_exchange uses sorted collections of these entries."""
        entries = [
            OrderExpirationEntry("BTC-USDT", "ord-z", 1.0, 300.0),
            OrderExpirationEntry("BTC-USDT", "ord-a", 1.0, 100.0),
            OrderExpirationEntry("BTC-USDT", "ord-m", 1.0, 200.0),
        ]
        sorted_entries = sorted(entries)
        expiry_seq = [e.expiration_timestamp for e in sorted_entries]
        assert expiry_seq == sorted(expiry_seq)


# ---------------------------------------------------------------------------
# Equality and hashing
# ---------------------------------------------------------------------------


class TestEqualityAndHash:
    def test_equal_entries(self, entry: OrderExpirationEntry) -> None:
        other = OrderExpirationEntry(
            entry.trading_pair,
            entry.order_id,
            entry.timestamp,
            entry.expiration_timestamp,
        )
        assert entry == other

    def test_different_trading_pair_not_equal(self, entry: OrderExpirationEntry) -> None:
        other = OrderExpirationEntry(
            "ETH-USDT", entry.order_id, entry.timestamp, entry.expiration_timestamp
        )
        assert entry != other

    def test_different_order_id_not_equal(self, entry: OrderExpirationEntry) -> None:
        other = OrderExpirationEntry(
            entry.trading_pair, "other", entry.timestamp, entry.expiration_timestamp
        )
        assert entry != other

    def test_not_equal_to_non_entry(self, entry: OrderExpirationEntry) -> None:
        assert entry != "not an entry"
        assert entry != 42

    def test_hashable(self, entry: OrderExpirationEntry) -> None:
        s = {entry}
        assert entry in s

    def test_equal_entries_same_hash(self, entry: OrderExpirationEntry) -> None:
        other = OrderExpirationEntry(
            entry.trading_pair,
            entry.order_id,
            entry.timestamp,
            entry.expiration_timestamp,
        )
        assert hash(entry) == hash(other)


# ---------------------------------------------------------------------------
# to_pandas
# ---------------------------------------------------------------------------


class TestToPandas:
    def test_to_pandas_columns(self) -> None:
        pd = pytest.importorskip("pandas", reason="pandas not installed")
        entries = [
            OrderExpirationEntry("BTC-USDT", "ord-1", 1000.0, 2000.0),
            OrderExpirationEntry("ETH-USDT", "ord-2", 1001.0, 2001.0),
        ]
        df = OrderExpirationEntry.to_pandas(entries)
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["trading_pair", "order_id", "timestamp", "expiration_timestamp"]

    def test_to_pandas_row_count(self) -> None:
        pytest.importorskip("pandas", reason="pandas not installed")
        entries = [
            OrderExpirationEntry("BTC-USDT", f"ord-{i}", float(i), float(i + 100)) for i in range(5)
        ]
        df = OrderExpirationEntry.to_pandas(entries)
        assert len(df) == 5

    def test_to_pandas_values(self) -> None:
        pytest.importorskip("pandas", reason="pandas not installed")
        entries = [OrderExpirationEntry("BTC-USDT", "ord-1", 1000.0, 2000.0)]
        df = OrderExpirationEntry.to_pandas(entries)
        row = df.iloc[0]
        assert row["trading_pair"] == "BTC-USDT"
        assert row["order_id"] == "ord-1"
        assert row["timestamp"] == pytest.approx(1000.0)
        assert row["expiration_timestamp"] == pytest.approx(2000.0)

    def test_to_pandas_empty_list(self) -> None:
        pytest.importorskip("pandas", reason="pandas not installed")
        df = OrderExpirationEntry.to_pandas([])
        assert len(df) == 0
        assert list(df.columns) == ["trading_pair", "order_id", "timestamp", "expiration_timestamp"]

    def test_to_pandas_no_expiration_or_expiration_time_column(self) -> None:
        """Verify the original Cython bug is fixed — no ghost columns."""
        pytest.importorskip("pandas", reason="pandas not installed")
        entries = [OrderExpirationEntry("BTC-USDT", "ord-1", 1.0, 2.0)]
        df = OrderExpirationEntry.to_pandas(entries)
        assert "expiration" not in df.columns
        assert "expiration_time" not in df.columns


# ---------------------------------------------------------------------------
# is_accelerated helper
# ---------------------------------------------------------------------------


class TestIsAccelerated:
    def test_returns_bool(self) -> None:
        result = is_accelerated()
        assert isinstance(result, bool)


class TestRustEqHash:
    """Validate __eq__ and __hash__ exist on the Rust backend (if available)."""

    def test_eq_same_fields(self):
        a = OrderExpirationEntry("BTC-USDT", "ord-1", 1000.0, 2000.0)
        b = OrderExpirationEntry("BTC-USDT", "ord-1", 1000.0, 2000.0)
        assert a == b

    def test_eq_different_fields(self):
        a = OrderExpirationEntry("BTC-USDT", "ord-1", 1000.0, 2000.0)
        b = OrderExpirationEntry("ETH-USDT", "ord-1", 1000.0, 2000.0)
        assert a != b

    def test_hash_consistent(self):
        a = OrderExpirationEntry("BTC-USDT", "ord-1", 1000.0, 2000.0)
        b = OrderExpirationEntry("BTC-USDT", "ord-1", 1000.0, 2000.0)
        assert hash(a) == hash(b)

    def test_hashable_in_set(self):
        a = OrderExpirationEntry("BTC-USDT", "ord-1", 1000.0, 2000.0)
        s = {a}
        assert a in s


def _load_python_fallback_class() -> type:
    """Load the pure-Python fallback class even when the Rust backend is present.

    The fallback is only defined in the module's ``except ImportError`` branch, so
    re-execute the module source with ``_core`` blocked from importing.
    """
    import importlib.util
    import sys

    mod = importlib.import_module("rust_accelerators.order_expiration_entry")

    spec = importlib.util.spec_from_file_location("_oee_python_fallback", mod.__file__)
    assert spec is not None and spec.loader is not None
    fallback_mod = importlib.util.module_from_spec(spec)
    saved = sys.modules.get("rust_accelerators._core", ...)
    sys.modules["rust_accelerators._core"] = None  # type: ignore[assignment]
    try:
        spec.loader.exec_module(fallback_mod)
    finally:
        if saved is ...:
            del sys.modules["rust_accelerators._core"]
        else:
            sys.modules["rust_accelerators._core"] = saved
    assert fallback_mod.is_accelerated() is False
    return fallback_mod.OrderExpirationEntry


class TestReprParityWithPythonFallback:
    """Rust __repr__ must be byte-identical to the Python fallback's __repr__."""

    @pytest.mark.parametrize(
        "value",
        [0.0, -0.0, 0.1, 1700000000.0, 1700000000.123456, 1e16, 1.5e-7, float("inf")],
    )
    def test_repr_matches_fallback(self, value: float) -> None:
        pytest.importorskip("rust_accelerators._core", reason="_core not importable")
        from rust_accelerators._core import order_expiration_entry as rust_oee

        rust_cls = rust_oee.OrderExpirationEntry
        py_cls = _load_python_fallback_class()
        assert repr(rust_cls("BTC-USDT", "ord-1", value, value)) == repr(
            py_cls("BTC-USDT", "ord-1", value, value)
        )
