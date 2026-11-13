# Parity Test Suite Design — hb-rust-accelerators

## Purpose

Define a reusable parity testing methodology that validates Rust implementations produce identical results to their Python fallbacks. Metrics and order_expiration_entry serve as reference implementations of this pattern; future modules follow the same template.

## Context

hb-rust-accelerators is a scaffold/staging repo. Modules are developed and validated here, then imported by an orchestrator session into hummingbot proper. After full validation, modules are cleaned up from this repo. All test infrastructure must be designed as reusable templates.

Current state:
- Two modules implemented: `metrics` (4 numeric functions) and `order_expiration_entry` (value-type class)
- Existing `tests/unit/` tests only exercise the pure Python fallback path
- The `_ACCELERATED = True` branches are untested
- Coverage target: >80% on `python/rust_accelerators/`

## Design Decisions

1. **Hard-require Rust**: Parity tests import `rust_accelerators._core` directly at module level. No `pytest.importorskip`, no skip-on-missing. If Rust isn't built, test collection fails with ImportError. This is a Rust-primary project.
2. **Approximate equality**: Use `pytest.approx(rel=1e-9)` for numeric comparisons. Rust (Welford's algorithm) and Python (`np.std`) produce algebraically equivalent but floating-point-different results.
3. **Separate directory**: `tests/parity/` — clean separation from CI-friendly fallback tests in `tests/unit/`.
4. **Extract pure Python fallbacks**: Every module must have a `_pure_<module>.py` file with the fallback implementation, importable independently of the `_ACCELERATED` flag. This enables dual-import without mock tricks.

## Directory Structure

```
tests/
├── parity/
│   ├── __init__.py
│   ├── conftest.py                             # Reusable parity helpers + data generators
│   ├── test_metrics_parity.py                  # Template: numeric function parity
│   └── test_order_expiration_entry_parity.py   # Template: class/object parity
├── unit/           # existing, unchanged
└── benchmarks/     # existing, unchanged
```

## Scaffold Standard

Every module scaffolded in this repo must produce:

1. `python/rust_accelerators/<module>.py` — wrapper with `_ACCELERATED` flag
2. `python/rust_accelerators/_pure_<module>.py` — pure Python fallback (always importable)
3. `src/<module>.rs` — Rust implementation
4. `tests/unit/test_<module>.py` — fallback tests (no Rust required)
5. `tests/parity/test_<module>_parity.py` — parity contract tests (Rust required)

## Reusable Infrastructure (`conftest.py`)

### `assert_numeric_parity(rust_fn, py_fn, *args, rel=1e-9)`

Calls both functions with identical arguments. Handles scalar and tuple returns. Asserts `pytest.approx` match.

### `assert_object_parity(rust_obj, py_obj, fields)`

Field-by-field comparison for class-based modules. Uses `isinstance(val, float)` to detect numeric fields and applies `pytest.approx` for those; exact match for strings and other types. This type-based detection ensures the helper works for future modules without hardcoding field names.

### `generate_numeric_data(n, seed=42, dtype=np.float64)`

Deterministic numpy array generator for reproducible test data. Used by parametrized standard-data fixtures (n=100, 1000, 10000). Edge case and stress test data uses inline numpy literals for readability.

### Hard import

```python
import rust_accelerators._core as _core  # Fails collection if Rust not built
```

## Metrics Parity Tests

### Functions under test

| Function | Signature | Return |
|----------|-----------|--------|
| `calculate_max_drawdown` | `(pnl_series: ndarray)` | `(float, float)` |
| `calculate_sharpe_ratio` | `(returns: ndarray, periods_per_year=252)` | `float` |
| `calculate_profit_factor` | `(pnl_values: ndarray)` | `float` |
| `calculate_all_metrics` | `(pnl_series: ndarray, periods_per_year=252)` | `(float, float, float, float)` |

### Import strategy

- Rust: `from rust_accelerators._core import calculate_max_drawdown as rs_calculate_max_drawdown`
- Python: `from rust_accelerators.metrics import calculate_max_drawdown as py_calculate_max_drawdown` with `_ACCELERATED` patched to `False`, or direct import from the pure Python function bodies

Since `metrics.py` defines the pure Python functions inline (not extracted to `_pure_metrics.py` yet), the parity tests can either:
- (a) Temporarily patch `_ACCELERATED = False` and re-import, or
- (b) Extract to `_pure_metrics.py` as part of this work

Option (b) is consistent with the scaffold standard but is a larger refactor. Option (a) works because the Python functions are already standalone — the `if _ACCELERATED` guard is at the call site, not the definition. The pure Python code paths are the `else` branches of each function. We can call them directly by setting `_ACCELERATED = False` on the module before importing.

**Chosen approach**: For metrics, use `monkeypatch.setattr(rust_accelerators.metrics, '_ACCELERATED', False)` in a pytest fixture. The `monkeypatch` fixture automatically restores the original value on teardown, preventing test pollution across the session. The wrapper then routes to the pure Python code paths. This avoids extracting `_pure_metrics.py` since the functions are already inline.

**Exception to scaffold standard**: Modules where the pure Python functions are defined inline in the wrapper (not in a class `except` block) may use the `monkeypatch` approach instead of extracting a `_pure_<module>.py` file. Class-based modules (like OEE) where the fallback is defined inside `except ImportError` must use the `_pure_*` extraction.

### Note on `calculate_all_metrics`

The Rust implementation computes all four metrics in a single pass, applying Welford's to the full `pnl_series`. The Python fallback calls `calculate_sharpe_ratio(pnl_series, ...)` — passing cumulative P&L to a function that semantically expects *returns*. This is a shared quirk in both implementations, not a parity gap. The parity test validates that both backends produce the same output for the same input, including this semantic behavior. Fixing the semantic question (Sharpe on cumulative P&L vs returns) is out of scope for this spec.

### Test data

| Category | Data | Purpose |
|----------|------|---------|
| Standard | `np.random.default_rng(42).normal(0.001, 0.02, n)` for n in [100, 1000, 10000] | Realistic trading data |
| Edge: empty | `np.array([], dtype=np.float64)` | Zero-length handling |
| Edge: single | `np.array([42.0])` | Minimum viable input |
| Edge: constant | `np.array([1.0, 1.0, 1.0, 1.0])` | Zero variance |
| Edge: all positive | `np.array([1.0, 2.0, 3.0])` | No losses |
| Edge: all negative | `np.array([-1.0, -2.0, -3.0])` | No wins |
| Stress: large values | `np.array([1e15, 2e15, 1.5e15])` | Overflow risk |
| Stress: small values | `np.array([1e-15, 2e-15, 1.5e-15])` | Underflow risk |

### Pattern

```python
def test_max_drawdown_parity(pnl_series):
    rust_result = rs_calculate_max_drawdown(pnl_series)
    py_result = py_calculate_max_drawdown(pnl_series)
    assert rust_result == pytest.approx(py_result, rel=1e-9)
```

## Order Expiration Entry Parity Tests

### Import strategy

Extract `OrderExpirationEntry` fallback class to `python/rust_accelerators/_pure_order_expiration_entry.py`. The wrapper module imports from `_pure_*` in the `except ImportError` block. Parity tests import both:

```python
from rust_accelerators._core.order_expiration_entry import OrderExpirationEntry as RustOEE
from rust_accelerators._pure_order_expiration_entry import OrderExpirationEntry as PyOEE
```

### API surface

| Aspect | Test approach |
|--------|--------------|
| Construction | Same args → same property values (field-by-field) |
| Properties | `trading_pair`, `order_id`, `timestamp`, `expiration_timestamp` match |
| `__lt__` ordering | Same list of entries → same sort order |
| `__eq__` | Same fields → both report equal (within own type). **Requires adding `__eq__` to Rust source.** |
| `__hash__` | Hashable + self-consistent: `hash(entry) == hash(identical_entry)` within each backend. Cross-backend numeric hash equality is NOT tested (CPython hash is not stable across language boundaries). Test that both backends produce usable dict keys/set members. **Requires adding `__hash__` to Rust source.** |
| `__repr__` | Identical string output |
| `to_pandas` | Identical DataFrame (columns, values, dtypes). Guard with `pytest.importorskip("pandas")` — pandas is not a declared dependency. |

### Pattern

```python
def test_construction_parity():
    rust_entry = RustOEE("BTC-USDT", "ord-1", 1000.0, 2000.0)
    py_entry = PyOEE("BTC-USDT", "ord-1", 1000.0, 2000.0)
    assert rust_entry.trading_pair == py_entry.trading_pair
    assert rust_entry.order_id == py_entry.order_id
    assert rust_entry.timestamp == pytest.approx(py_entry.timestamp)
    assert rust_entry.expiration_timestamp == pytest.approx(py_entry.expiration_timestamp)
```

## Coverage & Integration

### pytest marker

```ini
[tool.pytest.ini_options]
markers = [
    "parity: Rust vs Python parity contract tests (require Rust built)",
]
```

### pixi tasks

No new tasks needed. Existing `rust-test` (`pytest tests/` depends-on `rust-build`) already runs parity tests. Selective run: `pytest -m parity` or `pytest -m "not parity"`.

## Files Changed/Created

| File | Action | Role |
|------|--------|------|
| `tests/parity/__init__.py` | Create | Package marker |
| `tests/parity/conftest.py` | Create | Reusable parity helpers |
| `tests/parity/test_metrics_parity.py` | Create | Template: numeric function parity |
| `tests/parity/test_order_expiration_entry_parity.py` | Create | Template: class/object parity |
| `python/rust_accelerators/_pure_order_expiration_entry.py` | Create | Extracted fallback class |
| `python/rust_accelerators/order_expiration_entry.py` | Edit | Import fallback from `_pure_*` |
| `src/order_expiration_entry.rs` | Edit | Add `__eq__` and `__hash__` implementations |
| `pyproject.toml` | Edit | Add `parity` marker |

## Success Criteria

1. All parity tests pass when Rust is built (`pixi run rust-test`)
2. Parity tests fail clearly with ImportError when Rust is not built
3. Existing `tests/unit/` tests remain unaffected
4. Coverage on `python/rust_accelerators/` exceeds 80%
5. Pattern is documented and repeatable for future modules
