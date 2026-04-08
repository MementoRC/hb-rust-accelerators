# tests/unit/test_test_migration.py
"""Tests for test-migration wire/unwire and status transitions."""

from __future__ import annotations

from scripts.migration_config import MigrationStatus, read_status, write_status
from scripts.test_migration import (
    unwire_module,
    wire_module,
)


class TestWireModule:
    def test_wire_adds_mod_and_submodule(self, tmp_path):
        lib_rs = tmp_path / "src" / "lib.rs"
        lib_rs.parent.mkdir(parents=True)
        lib_rs.write_text(
            "use pyo3::prelude::*;\n\n"
            "#[pymodule]\n"
            "fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {\n"
            "    m.add_function(wrap_pyfunction!(calculate_max_drawdown, m)?)?;\n"
            "    Ok(())\n"
            "}\n"
        )
        wire_module(tmp_path, "pubsub", tmp_path / "migrations" / "pubsub" / "src" / "lib.rs")
        result = lib_rs.read_text()
        assert '#[path = "' in result or "mod pubsub;" in result
        assert "pubsub::register" in result

    def test_unwire_removes_additions(self, tmp_path):
        lib_rs = tmp_path / "src" / "lib.rs"
        lib_rs.parent.mkdir(parents=True)
        original = (
            "use pyo3::prelude::*;\n\n"
            "#[pymodule]\n"
            "fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {\n"
            "    m.add_function(wrap_pyfunction!(calculate_max_drawdown, m)?)?;\n"
            "    Ok(())\n"
            "}\n"
        )
        lib_rs.write_text(original)
        wire_module(tmp_path, "pubsub", tmp_path / "migrations" / "pubsub" / "src" / "lib.rs")
        unwire_module(tmp_path, "pubsub")
        result = lib_rs.read_text()
        assert result == original

    def test_wire_uses_relative_path(self, tmp_path):
        lib_rs = tmp_path / "src" / "lib.rs"
        lib_rs.parent.mkdir(parents=True)
        lib_rs.write_text(
            "use pyo3::prelude::*;\n\n"
            "#[pymodule]\n"
            "fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {\n"
            "    Ok(())\n"
            "}\n"
        )
        module_src = tmp_path / "migrations" / "pubsub" / "src" / "lib.rs"
        module_src.parent.mkdir(parents=True)
        module_src.write_text("pub fn register() {}")
        wire_module(tmp_path, "pubsub", module_src)
        result = lib_rs.read_text()
        # path attribute must be relative (no leading /)
        import re

        path_match = re.search(r'#\[path = "([^"]+)"\]', result)
        assert path_match is not None
        assert not path_match.group(1).startswith("/"), "path attribute must be relative"

    def test_recovery_unwires_if_already_wired(self, tmp_path):
        from scripts.test_migration import run_test_migration

        lib_rs = tmp_path / "src" / "lib.rs"
        lib_rs.parent.mkdir(parents=True)
        original = (
            "use pyo3::prelude::*;\n\n"
            "#[pymodule]\n"
            "fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {\n"
            "    Ok(())\n"
            "}\n"
        )
        lib_rs.write_text(original)
        # Simulate a previously wired state (as if a prior run crashed)
        wire_module(tmp_path, "pubsub", tmp_path / "migrations" / "pubsub" / "src" / "lib.rs")
        wired_text = lib_rs.read_text()
        assert "MIGRATION WIRE START: pubsub" in wired_text

        # Create a minimal migration dir so run_test_migration can enter
        m_dir = tmp_path / "migrations" / "pubsub"
        m_dir.mkdir(parents=True, exist_ok=True)
        (m_dir / "src").mkdir(exist_ok=True)
        (m_dir / "src" / "lib.rs").write_text("pub fn register() {}")
        from scripts.migration_config import MigrationStatus, write_status

        write_status(
            m_dir,
            MigrationStatus(
                issue_number=20,
                module="hummingbot.core.pubsub",
                status="scaffolded",
                created="2026-04-07",
                source_files=[],
                tier=3,
            ),
        )

        # run_test_migration should detect the wired state and unwire before proceeding
        # (It will fail at the build step since there's no real pixi/maturin, but the
        # recovery unwire happens before the build subprocess call.)
        run_test_migration("pubsub", project_root=tmp_path)
        # After run_test_migration (which always unwires in finally), lib.rs should be clean
        result = lib_rs.read_text()
        assert "MIGRATION WIRE START: pubsub" not in result


class TestStatusTransitions:
    def _make_migration(self, tmp_path, status="scaffolded"):
        m_dir = tmp_path / "migrations" / "pubsub"
        m_dir.mkdir(parents=True)
        (m_dir / "src").mkdir()
        (m_dir / "tests").mkdir()
        s = MigrationStatus(
            issue_number=20,
            module="hummingbot.core.pubsub",
            status=status,
            created="2026-04-07",
            source_files=[],
            tier=3,
        )
        write_status(m_dir, s)
        return m_dir

    def test_scaffolded_to_in_progress_on_first_run(self, tmp_path):
        from scripts.test_migration import update_status_for_run

        m_dir = self._make_migration(tmp_path, "scaffolded")
        update_status_for_run(m_dir, test_passed=False)
        assert read_status(m_dir).status == "in_progress"

    def test_in_progress_to_tests_passing_on_success(self, tmp_path):
        from scripts.test_migration import update_status_for_run

        m_dir = self._make_migration(tmp_path, "in_progress")
        update_status_for_run(m_dir, test_passed=True)
        assert read_status(m_dir).status == "tests_passing"

    def test_stays_tests_passing_on_repeated_success(self, tmp_path):
        from scripts.test_migration import update_status_for_run

        m_dir = self._make_migration(tmp_path, "tests_passing")
        update_status_for_run(m_dir, test_passed=True)
        assert read_status(m_dir).status == "tests_passing"

    def test_reverts_to_in_progress_on_failure(self, tmp_path):
        from scripts.test_migration import update_status_for_run

        m_dir = self._make_migration(tmp_path, "tests_passing")
        update_status_for_run(m_dir, test_passed=False)
        assert read_status(m_dir).status == "in_progress"
