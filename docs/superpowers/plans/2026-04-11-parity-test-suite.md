# Parity Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable parity testing methodology that validates Rust implementations match Python fallbacks, using metrics and order_expiration_entry as reference templates.

**Architecture:** Separate `tests/parity/` directory with shared conftest helpers (`assert_numeric_parity`, `assert_object_parity`, `generate_numeric_data`). Metrics tests use `monkeypatch` to access the Python fallback path. OEE tests use an extracted `_pure_order_expiration_entry.py` module for dual-import. Rust `__eq__`/`__hash__` must be added to the OEE source before parity tests can run.

**Tech Stack:** pytest, numpy, PyO3/maturin, monkeypatch, pytest.approx(rel=1e-9)

**Spec:** `docs/superpowers/specs/2026-04-11-parity-test-suite-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/order_expiration_entry.rs` | Edit | Add `__eq__` and `__hash__` to Rust OEE class |
| `python/rust_accelerators/_pure_order_expiration_entry.py` | Create | Extracted pure Python OEE fallback class |
| `python/rust_accelerators/order_expiration_entry.py` | Edit | Import fallback from `_pure_*` instead of inline |
| `tests/parity/__init__.py` | Create | Package marker (empty) |
| `tests/parity/conftest.py` | Create | Reusable parity helpers + hard `_core` import |
| `tests/parity/test_metrics_parity.py` | Create | Numeric function parity template |
| `tests/parity/test_order_expiration_entry_parity.py` | Create | Class/object parity template |
| `pyproject.toml` | Edit | Add `parity` marker to `[tool.pytest.ini_options]` |

---

### Task 1: Add `__eq__` and `__hash__` to Rust OEE

**Files:**
- Modify: `src/order_expiration_entry.rs:25-92` (inside `#[pymethods] impl`)

- [ ] **Step 1: Write the failing test for `__eq__`**

Add to existing `tests/unit/test_order_expiration_entry.py` temporarily (the parity test can't exist yet):

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pixi run rust-test`
Expected: FAIL — `__eq__` not implemented on Rust class (returns `NotImplemented` or uses identity comparison, causing `a == b` to be `False`).

- [ ] **Step 3: Implement `__eq__` and `__hash__` in Rust**

Add these methods inside the `#[pymethods] impl OrderExpirationEntry` block in `src/order_expiration_entry.rs`, after the `__lt__` method:

```rust
    /// Equality comparison — matches Python fallback semantics.
    ///
    /// Two entries are equal iff all four fields match.
    pub fn __eq__(&self, other: &OrderExpirationEntry) -> bool {
        self.trading_pair == other.trading_pair
            && self.order_id == other.order_id
            && self.timestamp == other.timestamp
            && self.expiration_timestamp == other.expiration_timestamp
    }

    /// Hash — consistent with __eq__ (all four fields).
    /// PyO3 requires isize return (matches CPython's Py_hash_t).
    pub fn __hash__(&self) -> isize {
        use std::hash::{Hash, Hasher};
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        self.trading_pair.hash(&mut hasher);
        self.order_id.hash(&mut hasher);
        self.timestamp.to_bits().hash(&mut hasher);
        self.expiration_timestamp.to_bits().hash(&mut hasher);
        hasher.finish() as isize
    }
```

- [ ] **Step 4: Build and run test to verify it passes**

Run: `pixi run rust-test`
Expected: PASS — all 4 new tests pass, all existing tests still pass.

- [ ] **Step 5: Commit**

```
git add src/order_expiration_entry.rs tests/unit/test_order_expiration_entry.py
git commit -m "feat: add __eq__ and __hash__ to Rust OrderExpirationEntry"
```

---

### Task 2: Extract pure Python OEE fallback to `_pure_order_expiration_entry.py`

**Files:**
- Create: `python/rust_accelerators/_pure_order_expiration_entry.py`
- Modify: `python/rust_accelerators/order_expiration_entry.py:31-118`

- [ ] **Step 1: Run existing unit tests to establish baseline**

Run: `pixi run test-unit`
Expected: All tests in `tests/unit/test_order_expiration_entry.py` PASS.

- [ ] **Step 2: Create `_pure_order_expiration_entry.py`**

Extract the `OrderExpirationEntry` class from the `except ImportError` block of `order_expiration_entry.py` into a standalone module. This is a **move**, not a copy — the class body is identical:

```python
"""Pure Python fallback for OrderExpirationEntry.

Extracted as a standalone module so parity tests can import both the Rust
and Python implementations simultaneously without mock tricks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    import pandas as pd


class OrderExpirationEntry:
    """Pure-Python fallback for OrderExpirationEntry.

    Semantics match the original Cython/C++ implementation exactly:
    - Ordering via __lt__: primary key = expiration_timestamp, secondary = order_id
    - to_pandas: columns are trading_pair, order_id, timestamp, expiration_timestamp
    """

    __slots__ = ("_trading_pair", "_order_id", "_timestamp", "_expiration_timestamp")

    def __init__(
        self,
        trading_pair: str,
        order_id: str,
        timestamp: float,
        expiration_ts: float,
    ) -> None:
        self._trading_pair: str = trading_pair
        self._order_id: str = order_id
        self._timestamp: float = float(timestamp)
        self._expiration_timestamp: float = float(expiration_ts)

    @property
    def trading_pair(self) -> str:
        return self._trading_pair

    @property
    def order_id(self) -> str:
        return self._order_id

    @property
    def timestamp(self) -> float:
        return self._timestamp

    @property
    def expiration_timestamp(self) -> float:
        return self._expiration_timestamp

    def __repr__(self) -> str:
        return (
            f"OrderExpirationEntry('{self._trading_pair}', '{self._order_id}', "
            f"{self._timestamp}, '{self._expiration_timestamp}')"
        )

    def __lt__(self, other: "OrderExpirationEntry") -> bool:
        """C++ operator< semantics: sort by expiration_timestamp, then order_id."""
        if self._expiration_timestamp == other._expiration_timestamp:
            return self._order_id < other._order_id
        return self._expiration_timestamp < other._expiration_timestamp

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OrderExpirationEntry):
            return NotImplemented
        return (
            self._expiration_timestamp == other._expiration_timestamp
            and self._order_id == other._order_id
            and self._trading_pair == other._trading_pair
            and self._timestamp == other._timestamp
        )

    def __hash__(self) -> int:
        return hash((self._trading_pair, self._order_id, self._timestamp, self._expiration_timestamp))

    @classmethod
    def to_pandas(cls, order_expiration_entries: List["OrderExpirationEntry"]) -> "pd.DataFrame":
        """Convert a list of entries to a pandas DataFrame.

        Columns: trading_pair, order_id, timestamp, expiration_timestamp
        """
        import pandas as pd

        columns = ["trading_pair", "order_id", "timestamp", "expiration_timestamp"]
        data = [
            [
                entry.trading_pair,
                entry.order_id,
                entry.timestamp,
                entry.expiration_timestamp,
            ]
            for entry in order_expiration_entries
        ]
        return pd.DataFrame(data=data, columns=columns)
```

- [ ] **Step 3: Update `order_expiration_entry.py` to import from `_pure_*`**

Replace the inline class definition in the `except ImportError` block with an import:

```python
"""hummingbot.core.data_type.order_expiration_entry — Rust-accelerated with Python fallback.

Provides OrderExpirationEntry, a lightweight value type used by paper_trade_exchange
to track per-order expiration bookkeeping. Originally implemented as a Cython wrapper
around a C++ struct; replaced here with a pure-Python fallback and an optional
Rust-accelerated variant.

Public API (mirrors original Cython class):
    OrderExpirationEntry(trading_pair, order_id, timestamp, expiration_ts)
    .trading_pair       -> str
    .order_id           -> str
    .timestamp          -> float
    .expiration_timestamp -> float
    .__repr__()         -> str
    .__lt__(other)      -> bool   (sort by expiration_timestamp, then order_id)
    .to_pandas(entries) -> pd.DataFrame  (classmethod)
"""

from __future__ import annotations

try:
    from rust_accelerators._core.order_expiration_entry import OrderExpirationEntry  # noqa: F401

    _ACCELERATED = True
except ImportError:
    from rust_accelerators._pure_order_expiration_entry import OrderExpirationEntry  # noqa: F401

    _ACCELERATED = False


def is_accelerated() -> bool:
    """Return True if Rust acceleration is available for order_expiration_entry."""
    return _ACCELERATED
```

- [ ] **Step 4: Run existing unit tests to verify no regression**

Run: `pixi run test-unit`
Expected: All tests in `tests/unit/test_order_expiration_entry.py` PASS — behavior identical to before.

- [ ] **Step 5: Commit**

```
git add python/rust_accelerators/_pure_order_expiration_entry.py python/rust_accelerators/order_expiration_entry.py
git commit -m "refactor: extract OEE pure Python fallback to _pure_order_expiration_entry.py"
```

---

### Task 3: Create parity test infrastructure (`conftest.py` + marker)

**Files:**
- Create: `tests/parity/__init__.py`
- Create: `tests/parity/conftest.py`
- Modify: `pyproject.toml:127-132` (markers list)

- [ ] **Step 1: Create `tests/parity/__init__.py`**

Empty file:

```python
```

- [ ] **Step 2: Create `tests/parity/conftest.py`**

```python
"""Reusable parity test infrastructure.

Provides helpers for asserting Rust vs Python implementation parity.
This conftest is the template for all future module parity tests.
"""

from __future__ import annotations

import numpy as np
import pytest

import rust_accelerators._core as _core  # noqa: F401 — hard import; fails collection if Rust not built


def assert_numeric_parity(rust_fn, py_fn, *args, rel=1e-9):
    """Call both functions with identical args, assert results match.

    Handles scalar and tuple returns via pytest.approx.
    """
    rust_result = rust_fn(*args)
    py_result = py_fn(*args)
    assert rust_result == pytest.approx(py_result, rel=rel), (
        f"Parity failure:\n  Rust: {rust_result}\n  Python: {py_result}"
    )


def assert_object_parity(rust_obj, py_obj, fields):
    """Field-by-field comparison for class-based module parity.

    Uses isinstance to detect float fields and applies pytest.approx;
    exact match for all other types.
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


def generate_numeric_data(n, seed=42, dtype=np.float64):
    """Deterministic numpy array for reproducible parity tests.

    Used by parametrized standard-data fixtures.
    Edge/stress data should use inline literals for readability.
    """
    rng = np.random.default_rng(seed)
    return rng.normal(0.001, 0.02, n).astype(dtype)


# --- Standard data fixtures (parametrized by size) ---

STANDARD_SIZES = [100, 1_000, 10_000]


@pytest.fixture(params=STANDARD_SIZES, ids=[f"n={s}" for s in STANDARD_SIZES])
def pnl_series(request):
    """Cumulative P&L series for drawdown/all-metrics tests."""
    return np.cumsum(generate_numeric_data(request.param))


@pytest.fixture(params=STANDARD_SIZES, ids=[f"n={s}" for s in STANDARD_SIZES])
def returns_series(request):
    """Returns series for Sharpe ratio tests."""
    return generate_numeric_data(request.param)


@pytest.fixture(params=STANDARD_SIZES, ids=[f"n={s}" for s in STANDARD_SIZES])
def pnl_values(request):
    """Individual trade P&L values for profit factor tests."""
    rng = np.random.default_rng(42)
    return rng.normal(0.5, 10.0, request.param)
```

- [ ] **Step 3: Add `parity` marker to `pyproject.toml`**

In `pyproject.toml`, add `"parity: Rust vs Python parity contract tests (require Rust built)",` to the `markers` list in `[tool.pytest.ini_options]`. It goes after the existing markers.

The existing markers section at line 127 looks like:
```
markers = [
    "unit: marks tests as unit tests",
    "integration: marks tests as integration tests",
```

Add the new marker:
```
markers = [
    "unit: marks tests as unit tests",
    "integration: marks tests as integration tests",
    "parity: Rust vs Python parity contract tests (require Rust built)",
```

- [ ] **Step 4: Verify parity infrastructure loads (with Rust built)**

Run: `pixi run rust-build && python -c "import rust_accelerators._core; print('OK')"`
Expected: Prints `OK` — confirms _core is importable.

Then: `pixi run rust-test -- tests/parity/ --collect-only`
Expected: `no tests ran` (empty collection, but no ImportError).

- [ ] **Step 5: Commit**

```
git add tests/parity/__init__.py tests/parity/conftest.py pyproject.toml
git commit -m "feat: add parity test infrastructure with reusable helpers"
```

---

### Task 4: Write metrics parity tests

**Files:**
- Create: `tests/parity/test_metrics_parity.py`

- [ ] **Step 1: Write the parity test file**

```python
"""Metrics parity tests — Rust vs Python fallback.

Template for numeric function parity testing. Each test calls both the Rust
(_core) and Python (fallback) implementations with identical inputs and
asserts approximate equality.

This file serves as the reference template for future numeric module parity tests.
"""

from __future__ import annotations

import numpy as np
import pytest

import rust_accelerators.metrics as metrics_module
from rust_accelerators._core import (
    calculate_all_metrics as rs_calculate_all_metrics,
    calculate_max_drawdown as rs_calculate_max_drawdown,
    calculate_profit_factor as rs_calculate_profit_factor,
    calculate_sharpe_ratio as rs_calculate_sharpe_ratio,
)

from tests.parity.conftest import assert_numeric_parity


# ---------------------------------------------------------------------------
# Fixture: force Python fallback path via monkeypatch
# ---------------------------------------------------------------------------


@pytest.fixture()
def _force_python_fallback(monkeypatch):
    """Patch _ACCELERATED to False so wrapper functions route to pure Python."""
    monkeypatch.setattr(metrics_module, "_ACCELERATED", False)


# ---------------------------------------------------------------------------
# Convenience: Python-path function references
# ---------------------------------------------------------------------------


def py_calculate_max_drawdown(pnl_series):
    """Call metrics wrapper with _ACCELERATED=False (via fixture)."""
    return metrics_module.calculate_max_drawdown(pnl_series)


def py_calculate_sharpe_ratio(returns, periods_per_year=252):
    return metrics_module.calculate_sharpe_ratio(returns, periods_per_year)


def py_calculate_profit_factor(pnl_values):
    return metrics_module.calculate_profit_factor(pnl_values)


def py_calculate_all_metrics(pnl_series, periods_per_year=252):
    return metrics_module.calculate_all_metrics(pnl_series, periods_per_year)


# ===========================================================================
# Max Drawdown Parity
# ===========================================================================


@pytest.mark.parity
class TestMaxDrawdownParity:
    @pytest.mark.usefixtures("_force_python_fallback")
    def test_standard_data(self, pnl_series):
        assert_numeric_parity(rs_calculate_max_drawdown, py_calculate_max_drawdown, pnl_series)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_empty(self):
        data = np.array([], dtype=np.float64)
        assert_numeric_parity(rs_calculate_max_drawdown, py_calculate_max_drawdown, data)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_single_element(self):
        data = np.array([42.0])
        assert_numeric_parity(rs_calculate_max_drawdown, py_calculate_max_drawdown, data)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_monotonically_increasing(self):
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert_numeric_parity(rs_calculate_max_drawdown, py_calculate_max_drawdown, data)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_constant_values(self):
        data = np.array([1.0, 1.0, 1.0, 1.0])
        assert_numeric_parity(rs_calculate_max_drawdown, py_calculate_max_drawdown, data)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_large_values(self):
        data = np.array([1e15, 2e15, 1.5e15, 1.8e15])
        assert_numeric_parity(rs_calculate_max_drawdown, py_calculate_max_drawdown, data)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_small_values(self):
        data = np.array([1e-15, 2e-15, 1.5e-15, 1.8e-15])
        assert_numeric_parity(rs_calculate_max_drawdown, py_calculate_max_drawdown, data)


# ===========================================================================
# Sharpe Ratio Parity
# ===========================================================================


@pytest.mark.parity
class TestSharpeRatioParity:
    @pytest.mark.usefixtures("_force_python_fallback")
    def test_standard_data(self, returns_series):
        assert_numeric_parity(rs_calculate_sharpe_ratio, py_calculate_sharpe_ratio, returns_series)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_empty(self):
        data = np.array([], dtype=np.float64)
        assert_numeric_parity(rs_calculate_sharpe_ratio, py_calculate_sharpe_ratio, data)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_single_element(self):
        data = np.array([42.0])
        assert_numeric_parity(rs_calculate_sharpe_ratio, py_calculate_sharpe_ratio, data)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_zero_variance(self):
        data = np.array([1.0, 1.0, 1.0, 1.0])
        assert_numeric_parity(rs_calculate_sharpe_ratio, py_calculate_sharpe_ratio, data)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_custom_periods(self):
        data = np.array([0.01, -0.02, 0.015, -0.005, 0.03])
        assert_numeric_parity(rs_calculate_sharpe_ratio, py_calculate_sharpe_ratio, data, 12)


# ===========================================================================
# Profit Factor Parity
# ===========================================================================


@pytest.mark.parity
class TestProfitFactorParity:
    @pytest.mark.usefixtures("_force_python_fallback")
    def test_standard_data(self, pnl_values):
        assert_numeric_parity(rs_calculate_profit_factor, py_calculate_profit_factor, pnl_values)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_empty(self):
        data = np.array([], dtype=np.float64)
        assert_numeric_parity(rs_calculate_profit_factor, py_calculate_profit_factor, data)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_all_positive(self):
        data = np.array([1.0, 2.0, 3.0])
        assert_numeric_parity(rs_calculate_profit_factor, py_calculate_profit_factor, data)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_all_negative(self):
        data = np.array([-1.0, -2.0, -3.0])
        assert_numeric_parity(rs_calculate_profit_factor, py_calculate_profit_factor, data)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_large_values(self):
        data = np.array([1e15, -2e15, 1.5e15])
        assert_numeric_parity(rs_calculate_profit_factor, py_calculate_profit_factor, data)


# ===========================================================================
# All Metrics Parity
# ===========================================================================


@pytest.mark.parity
class TestAllMetricsParity:
    @pytest.mark.usefixtures("_force_python_fallback")
    def test_standard_data(self, pnl_series):
        assert_numeric_parity(rs_calculate_all_metrics, py_calculate_all_metrics, pnl_series)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_empty(self):
        data = np.array([], dtype=np.float64)
        assert_numeric_parity(rs_calculate_all_metrics, py_calculate_all_metrics, data)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_single_element(self):
        data = np.array([42.0])
        assert_numeric_parity(rs_calculate_all_metrics, py_calculate_all_metrics, data)

    @pytest.mark.usefixtures("_force_python_fallback")
    def test_custom_periods(self):
        data = np.array([50.0, 100.0, 80.0, 90.0, 95.0])
        assert_numeric_parity(rs_calculate_all_metrics, py_calculate_all_metrics, data, 12)
```

- [ ] **Step 2: Run parity tests to verify they pass**

Run: `pixi run rust-test -- tests/parity/test_metrics_parity.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```
git add tests/parity/test_metrics_parity.py
git commit -m "feat: add metrics parity tests (Rust vs Python template)"
```

---

### Task 5: Write OEE parity tests

**Files:**
- Create: `tests/parity/test_order_expiration_entry_parity.py`

- [ ] **Step 1: Write the parity test file**

```python
"""OrderExpirationEntry parity tests — Rust vs Python fallback.

Template for class/object parity testing. Each test creates both a Rust-backed
and Python-backed instance with identical constructor args, then asserts
behavioral equivalence across the full API surface.

This file serves as the reference template for future class-based module parity tests.
"""

from __future__ import annotations

import pytest

from rust_accelerators._core.order_expiration_entry import (
    OrderExpirationEntry as RustOEE,
)
from rust_accelerators._pure_order_expiration_entry import (
    OrderExpirationEntry as PyOEE,
)

from tests.parity.conftest import assert_object_parity

OEE_FIELDS = ("trading_pair", "order_id", "timestamp", "expiration_timestamp")


# ---------------------------------------------------------------------------
# Construction & Properties Parity
# ---------------------------------------------------------------------------


@pytest.mark.parity
class TestConstructionParity:
    def test_basic_construction(self):
        assert_object_parity(
            RustOEE("BTC-USDT", "ord-1", 1000.0, 2000.0),
            PyOEE("BTC-USDT", "ord-1", 1000.0, 2000.0),
            OEE_FIELDS,
        )

    def test_default_values(self):
        assert_object_parity(
            RustOEE("", "", 0.0, 0.0),
            PyOEE("", "", 0.0, 0.0),
            OEE_FIELDS,
        )

    def test_int_timestamps_coerced(self):
        assert_object_parity(
            RustOEE("BTC-USDT", "x", 1000, 2000),
            PyOEE("BTC-USDT", "x", 1000, 2000),
            OEE_FIELDS,
        )

    def test_empty_order_id(self):
        assert_object_parity(
            RustOEE("BTC-USDT", "", 1.0, 2.0),
            PyOEE("BTC-USDT", "", 1.0, 2.0),
            OEE_FIELDS,
        )


# ---------------------------------------------------------------------------
# __repr__ Parity
# ---------------------------------------------------------------------------


@pytest.mark.parity
class TestReprParity:
    def test_repr_basic(self):
        rust_repr = repr(RustOEE("BTC-USDT", "ord-1", 1000.0, 2000.0))
        py_repr = repr(PyOEE("BTC-USDT", "ord-1", 1000.0, 2000.0))
        assert rust_repr == py_repr

    def test_repr_empty(self):
        rust_repr = repr(RustOEE("", "", 0.0, 0.0))
        py_repr = repr(PyOEE("", "", 0.0, 0.0))
        assert rust_repr == py_repr

    def test_repr_large_timestamp(self):
        # NOTE: Rust f64 Display and Python float may format differently
        # (e.g., Rust: "1000" vs Python: "1000.0"). If this test fails,
        # align __repr__ formatting in src/order_expiration_entry.rs to
        # match Python's float output (e.g., use `:?` or manual formatting).
        rust_repr = repr(RustOEE("ETH-USDT", "ord-99", 1_700_000_000.0, 1_700_000_060.0))
        py_repr = repr(PyOEE("ETH-USDT", "ord-99", 1_700_000_000.0, 1_700_000_060.0))
        assert rust_repr == py_repr


# ---------------------------------------------------------------------------
# __lt__ Ordering Parity
# ---------------------------------------------------------------------------


@pytest.mark.parity
class TestOrderingParity:
    def test_earlier_expiry_is_less(self):
        rust_a = RustOEE("BTC-USDT", "ord-1", 1.0, 100.0)
        rust_b = RustOEE("BTC-USDT", "ord-1", 1.0, 200.0)
        py_a = PyOEE("BTC-USDT", "ord-1", 1.0, 100.0)
        py_b = PyOEE("BTC-USDT", "ord-1", 1.0, 200.0)
        assert (rust_a < rust_b) == (py_a < py_b)

    def test_same_expiry_order_id_tiebreak(self):
        rust_a = RustOEE("X", "aaa", 1.0, 100.0)
        rust_b = RustOEE("X", "zzz", 1.0, 100.0)
        py_a = PyOEE("X", "aaa", 1.0, 100.0)
        py_b = PyOEE("X", "zzz", 1.0, 100.0)
        assert (rust_a < rust_b) == (py_a < py_b)
        assert (rust_b < rust_a) == (py_b < py_a)

    def test_sort_order_matches(self):
        """Sorting a list of entries should produce the same order in both backends."""
        args_list = [
            ("X", "b", 1.0, 200.0),
            ("X", "a", 1.0, 100.0),
            ("X", "c", 1.0, 200.0),
            ("Y", "d", 1.0, 50.0),
        ]
        rust_sorted = sorted(RustOEE(*a) for a in args_list)
        py_sorted = sorted(PyOEE(*a) for a in args_list)
        for rust_e, py_e in zip(rust_sorted, py_sorted):
            assert_object_parity(rust_e, py_e, OEE_FIELDS)


# ---------------------------------------------------------------------------
# __eq__ Parity (within each backend)
# ---------------------------------------------------------------------------


@pytest.mark.parity
class TestEqualityParity:
    def test_equal_entries(self):
        rust_a = RustOEE("BTC-USDT", "ord-1", 1000.0, 2000.0)
        rust_b = RustOEE("BTC-USDT", "ord-1", 1000.0, 2000.0)
        py_a = PyOEE("BTC-USDT", "ord-1", 1000.0, 2000.0)
        py_b = PyOEE("BTC-USDT", "ord-1", 1000.0, 2000.0)
        assert (rust_a == rust_b) == (py_a == py_b) == True  # noqa: E712

    def test_different_trading_pair(self):
        rust_a = RustOEE("BTC-USDT", "ord-1", 1000.0, 2000.0)
        rust_b = RustOEE("ETH-USDT", "ord-1", 1000.0, 2000.0)
        py_a = PyOEE("BTC-USDT", "ord-1", 1000.0, 2000.0)
        py_b = PyOEE("ETH-USDT", "ord-1", 1000.0, 2000.0)
        assert (rust_a == rust_b) == (py_a == py_b) == False  # noqa: E712

    def test_not_equal_to_non_entry(self):
        rust_e = RustOEE("BTC-USDT", "ord-1", 1.0, 2.0)
        py_e = PyOEE("BTC-USDT", "ord-1", 1.0, 2.0)
        assert (rust_e == "not an entry") == (py_e == "not an entry")
        assert (rust_e == 42) == (py_e == 42)


# ---------------------------------------------------------------------------
# __hash__ Parity (self-consistency only, NOT cross-backend numeric equality)
# ---------------------------------------------------------------------------


@pytest.mark.parity
class TestHashParity:
    def test_consistent_within_rust(self):
        a = RustOEE("BTC-USDT", "ord-1", 1000.0, 2000.0)
        b = RustOEE("BTC-USDT", "ord-1", 1000.0, 2000.0)
        assert hash(a) == hash(b)

    def test_consistent_within_python(self):
        a = PyOEE("BTC-USDT", "ord-1", 1000.0, 2000.0)
        b = PyOEE("BTC-USDT", "ord-1", 1000.0, 2000.0)
        assert hash(a) == hash(b)

    def test_usable_as_dict_key_rust(self):
        e = RustOEE("BTC-USDT", "ord-1", 1000.0, 2000.0)
        d = {e: "value"}
        assert d[e] == "value"

    def test_usable_as_set_member_python(self):
        e = PyOEE("BTC-USDT", "ord-1", 1000.0, 2000.0)
        s = {e}
        assert e in s


# ---------------------------------------------------------------------------
# to_pandas Parity
# ---------------------------------------------------------------------------


@pytest.mark.parity
class TestToPandasParity:
    def test_basic_dataframe(self):
        pd = pytest.importorskip("pandas", reason="pandas not installed")

        args_list = [
            ("BTC-USDT", "ord-1", 1000.0, 2000.0),
            ("ETH-USDT", "ord-2", 1001.0, 2001.0),
        ]
        rust_entries = [RustOEE(*a) for a in args_list]
        py_entries = [PyOEE(*a) for a in args_list]

        rust_df = RustOEE.to_pandas(rust_entries)
        py_df = PyOEE.to_pandas(py_entries)

        assert list(rust_df.columns) == list(py_df.columns)
        assert len(rust_df) == len(py_df)
        pd.testing.assert_frame_equal(rust_df, py_df)

    def test_empty_list(self):
        pd = pytest.importorskip("pandas", reason="pandas not installed")

        rust_df = RustOEE.to_pandas([])
        py_df = PyOEE.to_pandas([])

        assert list(rust_df.columns) == list(py_df.columns)
        assert len(rust_df) == len(py_df) == 0

    def test_single_entry(self):
        pd = pytest.importorskip("pandas", reason="pandas not installed")

        rust_df = RustOEE.to_pandas([RustOEE("BTC-USDT", "ord-1", 1.0, 2.0)])
        py_df = PyOEE.to_pandas([PyOEE("BTC-USDT", "ord-1", 1.0, 2.0)])

        pd.testing.assert_frame_equal(rust_df, py_df)
```

- [ ] **Step 2: Run parity tests to verify they pass**

Run: `pixi run rust-test -- tests/parity/test_order_expiration_entry_parity.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```
git add tests/parity/test_order_expiration_entry_parity.py
git commit -m "feat: add OEE parity tests (Rust vs Python template)"
```

---

### Task 6: Verify full suite and coverage

**Files:** No new files. Validation only.

- [ ] **Step 1: Run full test suite with Rust built**

Run: `pixi run rust-test`
Expected: All tests pass — unit, parity, and benchmarks (benchmarks skipped via `--benchmark-disable`).

- [ ] **Step 2: Run parity tests in isolation**

Run: `pixi run rust-build && pytest tests/ -m parity -v`
Expected: Only parity-marked tests run. All pass.

- [ ] **Step 3: Verify existing unit tests still pass without Rust**

Run: `pixi run test-unit`
Expected: All unit tests pass (they don't need Rust).

- [ ] **Step 4: Check coverage**

Run: `pixi run rust-build && pytest tests/ --cov=rust_accelerators --cov-report=term-missing`
Expected: Coverage on `python/rust_accelerators/` exceeds 80%. The `_ACCELERATED = True` branches are now exercised by parity tests.

- [ ] **Step 5: Commit (if any fixups needed)**

Only if adjustments were required. Otherwise this task is validation-only.

---

### Task 7: Remove temporary `__eq__`/`__hash__` tests from unit tests

**Files:**
- Modify: `tests/unit/test_order_expiration_entry.py`

- [ ] **Step 1: Remove the `TestRustEqHash` class from unit tests**

The `TestRustEqHash` class added in Task 1 was a temporary scaffold to drive the Rust implementation. Now that the parity tests cover `__eq__` and `__hash__` properly (in `TestEqualityParity` and `TestHashParity`), the temporary class in unit tests is redundant.

Remove the entire `TestRustEqHash` class from `tests/unit/test_order_expiration_entry.py`.

Note: Keep the existing `TestEqualityAndHash` class (search by class name, not line number — Task 1 shifted lines) — those test the Python fallback and are not redundant.

- [ ] **Step 2: Run full test suite to verify no regression**

Run: `pixi run rust-test`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```
git add tests/unit/test_order_expiration_entry.py
git commit -m "cleanup: remove temporary __eq__/__hash__ tests (covered by parity suite)"
```
