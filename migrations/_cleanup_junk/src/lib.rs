use pyo3::prelude::*;

/// Register _cleanup_junk types and functions on the given PyModule.
///
/// Called by the root _core module at integration time:
///   let m = PyModule::new(py, "_cleanup_junk")?;
///   _cleanup_junk::register(m.as_borrowed())?;
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // TODO: Register your #[pyclass] and #[pyfunction] items here
    // Example:
    //   m.add_class::<MyClass>()?;
    //   m.add_function(wrap_pyfunction!(my_function, m)?)?;
    Ok(())
}
