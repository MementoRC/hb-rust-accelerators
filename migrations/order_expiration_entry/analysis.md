Implementation target: Claude Code session in rust-accelerators.
Follow the metrics module pattern in src/lib.rs for PyO3 conventions.

# hummingbot.core.data_type.order_expiration_entry Migration Analysis

**Issue**: #21
**Tier**: 3
**Source files**:
- `hummingbot/core/cpp/OrderExpirationEntry.h`
- `hummingbot/core/cpp/OrderExpirationEntry.cpp`
- `hummingbot/core/data_type/order_expiration_entry.pyx`
- `hummingbot/core/data_type/order_expiration_entry.pxd`

## Original API Surface

### C++ Struct Fields (private)
| Field | Type | Description |
|-------|------|-------------|
| `tradingPair` | `std::string` | Trading pair identifier |
| `orderId` | `std::string` | Client order ID |
| `timestamp` | `double` | Order creation timestamp |
| `expiration_timestamp` | `double` | Order expiration timestamp |

### C++ Constructors
- `OrderExpirationEntry()` — default (all fields zeroed/empty)
- `OrderExpirationEntry(string tradingPair, string orderId, double timestamp, double expiration_timestamp)` — parameterized
- `OrderExpirationEntry(const OrderExpirationEntry &other)` — copy constructor
- `OrderExpirationEntry &operator=(const OrderExpirationEntry &other)` — copy assignment

### C++ Methods
| Method | Return | Description |
|--------|--------|-------------|
| `getTradingPair()` | `std::string` | Returns trading pair |
| `getClientOrderID()` | `std::string` | Returns client order ID |
| `getTimestamp()` | `double` | Returns creation timestamp |
| `getExpirationTimestamp()` | `double` | Returns expiration timestamp |
| `operator<` (friend) | `bool` | Sort by `expiration_timestamp`, then `orderId` |

### Python-facing API (Cython wrapper)
```python
class OrderExpirationEntry:
    def __init__(self, trading_pair: str, order_id: str, timestamp: float, expiration_ts: float): ...
    @property
    def trading_pair(self) -> str: ...
    @property
    def order_id(self) -> str: ...
    @property
    def timestamp(self) -> float: ...
    @property
    def expiration_timestamp(self) -> float: ...
    def __repr__(self) -> str: ...
    @classmethod
    def to_pandas(cls, order_expiration_entries: List[OrderExpirationEntry]) -> pd.DataFrame: ...
```

### Cython internal (not public Python)
```cython
cdef OrderExpirationEntry c_create_order_expiration_from_cpp_order_expiration(
    const CPPOrderExpirationEntry cpp_order_expiration_entry
)
```

## Data Structures

### C++ → Rust mapping

```rust
#[pyclass]
#[derive(Clone, Debug)]
pub struct OrderExpirationEntry {
    trading_pair: String,       // tradingPair
    order_id: String,           // orderId
    timestamp: f64,             // timestamp
    expiration_timestamp: f64,  // expiration_timestamp
}
```

PyO3 `#[pymethods]` needed:
- `#[new]` constructor: `(trading_pair, order_id, timestamp, expiration_ts)`
- `#[getter] trading_pair`, `order_id`, `timestamp`, `expiration_timestamp`
- `__repr__`
- `__lt__` (rich comparison): sort by `expiration_timestamp`, then `order_id`
- `to_pandas` classmethod (requires `pyo3` + optional `numpy`/`pandas` interop via Python call)

## Suggested Crate Dependencies

- `pyo3` (already in workspace) — Python bindings
- No additional crates needed; all fields are primitives + String

## Fallback Feasibility

**High feasibility** — pure-Python fallback is trivial:
```python
class OrderExpirationEntry:
    def __init__(self, trading_pair, order_id, timestamp, expiration_ts):
        self._trading_pair = trading_pair
        self._order_id = order_id
        self._timestamp = timestamp
        self._expiration_timestamp = expiration_ts
    # ... properties, __lt__, to_pandas
```
No numpy/scipy/complex dependencies. Fallback is ~30 lines of Python.

## Existing Tests

No dedicated test file found for `order_expiration_entry` in the hummingbot test suite.
Used by `paper_trade_exchange.pxd` as a type annotation only (cimport).
Tests can be written from scratch for the Rust implementation.

## Known Complexity

1. **`to_pandas` column name bug**: The `.pyx` `to_pandas` method references `expiration_entry.expiration` and `expiration_entry.expiration_time` — these fields do not exist on the class (only `expiration_timestamp` does). This is a latent bug in the original. The Rust migration should either:
   - Fix it (use `expiration_timestamp` for both or pick a consistent name), or
   - Preserve the bug for compatibility (attribute access will raise `AttributeError` at runtime)
   - **Recommendation**: fix it, document in PR.

2. **`operator<` ordering**: Must be preserved as `__lt__` for set/sorted usage in `paper_trade_exchange`.

3. **`c_create_order_expiration_from_cpp_order_expiration`**: This is a Cython-internal factory (cdef). Not needed in the Rust/Python implementation — constructors replace it.
