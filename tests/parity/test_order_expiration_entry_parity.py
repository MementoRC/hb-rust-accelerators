"""OrderExpirationEntry parity tests -- Rust (_core) vs the pure-Python class.

Reference template for class/object parity tests: each test builds a Rust-backed and
a Python-backed instance from identical constructor args and asserts equivalent
behaviour across the API surface. The Rust class comes from the ``rust_core``
fixture; the Python class is imported directly from its own module.
"""

from __future__ import annotations

import types

import pytest
from rust_accelerators._pure_order_expiration_entry import OrderExpirationEntry as PyOEE

from tests.parity.helpers import assert_object_parity

OEE_FIELDS = ("trading_pair", "order_id", "timestamp", "expiration_timestamp")

BASIC = ("BTC-USDT", "ord-1", 1000.0, 2000.0)


@pytest.fixture
def rust_oee(rust_core: types.ModuleType) -> type:
    return rust_core.order_expiration_entry.OrderExpirationEntry


@pytest.mark.parity
class TestConstructionParity:
    @pytest.mark.parametrize(
        "args",
        [
            pytest.param(BASIC, id="basic"),
            pytest.param(("", "", 0.0, 0.0), id="defaults"),
            pytest.param(("BTC-USDT", "x", 1000, 2000), id="int-timestamps"),
            pytest.param(("BTC-USDT", "", 1.0, 2.0), id="empty-order-id"),
        ],
    )
    def test_construction(self, rust_oee: type, args: tuple) -> None:
        assert_object_parity(rust_oee(*args), PyOEE(*args), OEE_FIELDS)

    def test_int_timestamps_become_float(self, rust_oee: type) -> None:
        rs, py = rust_oee("A", "x", 1000, 2000), PyOEE("A", "x", 1000, 2000)
        assert type(rs.timestamp) is type(py.timestamp) is float
        assert type(rs.expiration_timestamp) is type(py.expiration_timestamp) is float


@pytest.mark.parity
class TestReprParity:
    @pytest.mark.parametrize(
        "args",
        [
            pytest.param(BASIC, id="basic"),
            pytest.param(("", "", 0.0, 0.0), id="empty"),
            pytest.param(("ETH-USDT", "ord-99", 1_700_000_000.0, 1_700_000_060.0), id="large-ts"),
        ],
    )
    def test_repr(self, rust_oee: type, args: tuple) -> None:
        assert repr(rust_oee(*args)) == repr(PyOEE(*args))


@pytest.mark.parity
class TestOrderingParity:
    def test_earlier_expiry_is_less(self, rust_oee: type) -> None:
        rs_a, rs_b = (
            rust_oee("BTC-USDT", "ord-1", 1.0, 100.0),
            rust_oee("BTC-USDT", "ord-1", 1.0, 200.0),
        )
        py_a, py_b = PyOEE("BTC-USDT", "ord-1", 1.0, 100.0), PyOEE("BTC-USDT", "ord-1", 1.0, 200.0)
        assert (rs_a < rs_b) == (py_a < py_b)
        assert (rs_b < rs_a) == (py_b < py_a)

    def test_same_expiry_order_id_tiebreak(self, rust_oee: type) -> None:
        rs_a, rs_b = rust_oee("X", "aaa", 1.0, 100.0), rust_oee("X", "zzz", 1.0, 100.0)
        py_a, py_b = PyOEE("X", "aaa", 1.0, 100.0), PyOEE("X", "zzz", 1.0, 100.0)
        assert (rs_a < rs_b) == (py_a < py_b)
        assert (rs_b < rs_a) == (py_b < py_a)

    def test_sort_order_matches(self, rust_oee: type) -> None:
        args_list = [
            ("X", "b", 1.0, 200.0),
            ("X", "a", 1.0, 100.0),
            ("X", "c", 1.0, 200.0),
            ("Y", "d", 1.0, 50.0),
        ]
        rs_sorted = sorted(rust_oee(*a) for a in args_list)
        py_sorted = sorted(PyOEE(*a) for a in args_list)
        assert len(rs_sorted) == len(py_sorted)
        for rs, py in zip(rs_sorted, py_sorted, strict=True):
            assert_object_parity(rs, py, OEE_FIELDS)


@pytest.mark.parity
class TestEqualityParity:
    def test_equal_entries(self, rust_oee: type) -> None:
        assert (rust_oee(*BASIC) == rust_oee(*BASIC)) is (PyOEE(*BASIC) == PyOEE(*BASIC)) is True

    def test_different_trading_pair(self, rust_oee: type) -> None:
        other = ("ETH-USDT", *BASIC[1:])
        assert (rust_oee(*BASIC) == rust_oee(*other)) is (PyOEE(*BASIC) == PyOEE(*other)) is False

    def test_not_equal_to_non_entry(self, rust_oee: type) -> None:
        rs, py = rust_oee(*BASIC), PyOEE(*BASIC)
        assert (rs == "not an entry") == (py == "not an entry")
        assert (rs == 42) == (py == 42)


@pytest.mark.parity
class TestHashParity:
    """Self-consistency within each backend only; hash values are not compared across them."""

    def test_consistent_within_rust(self, rust_oee: type) -> None:
        assert hash(rust_oee(*BASIC)) == hash(rust_oee(*BASIC))

    def test_consistent_within_python(self) -> None:
        assert hash(PyOEE(*BASIC)) == hash(PyOEE(*BASIC))

    def test_usable_as_dict_key_rust(self, rust_oee: type) -> None:
        e = rust_oee(*BASIC)
        assert {e: "value"}[rust_oee(*BASIC)] == "value"

    def test_usable_as_set_member_python(self) -> None:
        assert PyOEE(*BASIC) in {PyOEE(*BASIC)}


@pytest.mark.parity
class TestToPandasParity:
    def test_basic_dataframe(self, rust_oee: type) -> None:
        pd = pytest.importorskip("pandas", reason="pandas not installed")
        args_list = [BASIC, ("ETH-USDT", "ord-2", 1001.0, 2001.0)]
        rs_df = rust_oee.to_pandas([rust_oee(*a) for a in args_list])
        py_df = PyOEE.to_pandas([PyOEE(*a) for a in args_list])
        assert list(rs_df.columns) == list(py_df.columns)
        pd.testing.assert_frame_equal(rs_df, py_df)

    def test_empty_list(self, rust_oee: type) -> None:
        pytest.importorskip("pandas", reason="pandas not installed")
        rs_df, py_df = rust_oee.to_pandas([]), PyOEE.to_pandas([])
        assert list(rs_df.columns) == list(py_df.columns)
        assert len(rs_df) == len(py_df) == 0

    def test_single_entry(self, rust_oee: type) -> None:
        pd = pytest.importorskip("pandas", reason="pandas not installed")
        pd.testing.assert_frame_equal(
            rust_oee.to_pandas([rust_oee("BTC-USDT", "ord-1", 1.0, 2.0)]),
            PyOEE.to_pandas([PyOEE("BTC-USDT", "ord-1", 1.0, 2.0)]),
        )
