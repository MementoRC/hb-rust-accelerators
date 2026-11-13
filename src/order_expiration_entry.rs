use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFloat, PyList, PyType};
use pyo3::Borrowed;

/// Rust implementation of hummingbot.core.data_type.OrderExpirationEntry.
///
/// Maps the C++ struct directly:
///   std::string tradingPair        → String
///   std::string orderId            → String
///   double      timestamp          → f64
///   double      expiration_timestamp → f64
///
/// Ordering (C++ operator<) is preserved as __lt__ (with __le__/__gt__/__ge__ on the same key):
///   primary key:   expiration_timestamp ascending
///   secondary key: order_id ascending (lexicographic)
#[pyclass(
    module = "rust_accelerators._core.order_expiration_entry",
    from_py_object
)]
#[derive(Clone, Debug)]
pub struct OrderExpirationEntry {
    trading_pair: String,
    order_id: String,
    timestamp: f64,
    expiration_timestamp: f64,
}

#[pymethods]
impl OrderExpirationEntry {
    /// Create a new OrderExpirationEntry.
    ///
    /// Args:
    ///     trading_pair:  Trading pair identifier (e.g. "BTC-USDT")
    ///     order_id:      Client order ID string
    ///     timestamp:     Order creation timestamp (Unix seconds)
    ///     expiration_ts: Order expiration timestamp (Unix seconds)
    #[new]
    pub fn new(trading_pair: String, order_id: String, timestamp: f64, expiration_ts: f64) -> Self {
        OrderExpirationEntry {
            trading_pair,
            order_id,
            timestamp,
            expiration_timestamp: expiration_ts,
        }
    }

    /// Trading pair identifier.
    #[getter]
    pub fn trading_pair(&self) -> &str {
        &self.trading_pair
    }

    /// Client order ID.
    #[getter]
    pub fn order_id(&self) -> &str {
        &self.order_id
    }

    /// Order creation timestamp (Unix seconds).
    #[getter]
    pub fn timestamp(&self) -> f64 {
        self.timestamp
    }

    /// Order expiration timestamp (Unix seconds).
    #[getter]
    pub fn expiration_timestamp(&self) -> f64 {
        self.expiration_timestamp
    }

    /// String representation matching the original Cython __repr__.
    ///
    /// Floats are formatted with Python's own float repr so the output is
    /// byte-identical to the pure-Python fallback (exponents, inf/nan, -0.0).
    pub fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let ts = PyFloat::new(py, self.timestamp).repr()?.to_string();
        let exp = PyFloat::new(py, self.expiration_timestamp)
            .repr()?
            .to_string();
        Ok(format!(
            "OrderExpirationEntry('{}', '{}', {}, '{}')",
            self.trading_pair, self.order_id, ts, exp
        ))
    }

    /// Rich comparison: less-than.
    ///
    /// Matches C++ operator<:
    ///   - primary sort key:   expiration_timestamp (ascending)
    ///   - secondary sort key: order_id (lexicographic ascending)
    pub fn __lt__(&self, other: &OrderExpirationEntry) -> bool {
        if self.expiration_timestamp == other.expiration_timestamp {
            self.order_id < other.order_id
        } else {
            self.expiration_timestamp < other.expiration_timestamp
        }
    }

    /// Equality comparison — matches Python fallback semantics.
    ///
    /// Two entries are equal iff all four fields match. Non-entry operands
    /// yield `NotImplemented` (PyO3 argument-extraction failure on comparison slots).
    pub fn __eq__(&self, other: &OrderExpirationEntry) -> bool {
        self.trading_pair == other.trading_pair
            && self.order_id == other.order_id
            && self.timestamp == other.timestamp
            && self.expiration_timestamp == other.expiration_timestamp
    }

    /// Hash — consistent with `__eq__` (all four fields).
    /// -0.0 is normalised to 0.0 because they compare equal.
    pub fn __hash__(&self) -> isize {
        use std::hash::{Hash, Hasher};
        let bits = |v: f64| (if v == 0.0 { 0.0_f64 } else { v }).to_bits();
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        self.trading_pair.hash(&mut hasher);
        self.order_id.hash(&mut hasher);
        bits(self.timestamp).hash(&mut hasher);
        bits(self.expiration_timestamp).hash(&mut hasher);
        hasher.finish() as isize
    }

    /// Rich comparison: less-than-or-equal (same key as `__lt__`).
    pub fn __le__(&self, other: &OrderExpirationEntry) -> bool {
        if self.expiration_timestamp == other.expiration_timestamp {
            self.order_id <= other.order_id
        } else {
            self.expiration_timestamp <= other.expiration_timestamp
        }
    }

    /// Rich comparison: greater-than (same key as `__lt__`).
    pub fn __gt__(&self, other: &OrderExpirationEntry) -> bool {
        if self.expiration_timestamp == other.expiration_timestamp {
            self.order_id > other.order_id
        } else {
            self.expiration_timestamp > other.expiration_timestamp
        }
    }

    /// Rich comparison: greater-than-or-equal (same key as `__lt__`).
    pub fn __ge__(&self, other: &OrderExpirationEntry) -> bool {
        if self.expiration_timestamp == other.expiration_timestamp {
            self.order_id >= other.order_id
        } else {
            self.expiration_timestamp >= other.expiration_timestamp
        }
    }

    /// Convert a list of OrderExpirationEntry objects to a pandas DataFrame.
    ///
    /// Columns: ["trading_pair", "order_id", "timestamp", "expiration_timestamp"]
    ///
    /// Note: the original Cython implementation referenced non-existent fields
    /// `expiration_entry.expiration` and `expiration_entry.expiration_time`.
    /// This implementation fixes that bug by using `expiration_timestamp` consistently.
    #[classmethod]
    pub fn to_pandas<'py>(
        _cls: &Bound<'py, PyType>,
        py: Python<'py>,
        order_expiration_entries: Vec<PyRef<'py, OrderExpirationEntry>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let pd = py.import("pandas")?;

        let columns = PyList::new(
            py,
            [
                "trading_pair",
                "order_id",
                "timestamp",
                "expiration_timestamp",
            ],
        )?;

        let data = PyList::empty(py);
        for entry in &order_expiration_entries {
            let row = PyList::new(
                py,
                [
                    entry.trading_pair.clone().into_pyobject(py)?.into_any(),
                    entry.order_id.clone().into_pyobject(py)?.into_any(),
                    entry.timestamp.into_pyobject(py)?.into_any(),
                    entry.expiration_timestamp.into_pyobject(py)?.into_any(),
                ],
            )?;
            data.append(row)?;
        }

        let kwargs = PyDict::new(py);
        kwargs.set_item("data", data)?;
        kwargs.set_item("columns", columns)?;
        pd.getattr("DataFrame")?.call((), Some(&kwargs))
    }
}

/// Register order_expiration_entry types on the given PyModule.
///
/// Called by the root _core module at integration time:
///   let sub = PyModule::new(m.py(), "order_expiration_entry")?;
///   order_expiration_entry::register(sub.as_borrowed())?;
///   m.add_submodule(&sub)?;
pub fn register(m: Borrowed<'_, '_, PyModule>) -> PyResult<()> {
    m.add_class::<OrderExpirationEntry>()?;
    Ok(())
}
