# tests/unit/test_integrate_module.py
"""Tests for module integration script."""

from __future__ import annotations

import json

from scripts.integrate_module import (
    merge_cargo_dependencies,
    promote_files,
    update_init_py,
    update_supersedes,
    wire_permanently,
)


class TestPromoteFiles:
    def _setup_migration(self, tmp_path):
        ws = tmp_path / "migrations" / "pubsub"
        (ws / "src").mkdir(parents=True)
        (ws / "python").mkdir(parents=True)
        (ws / "tests").mkdir(parents=True)
        (ws / "src" / "lib.rs").write_text("pub fn register() {}")
        (ws / "python" / "pubsub.py").write_text("# wrapper")
        (ws / "tests" / "test_pubsub.py").write_text("# tests")
        (ws / "analysis.md").write_text("# analysis")
        (ws / "status.json").write_text(
            json.dumps(
                {
                    "issue_number": 20,
                    "module": "hummingbot.core.pubsub",
                    "status": "tests_passing",
                    "created": "2026-04-07",
                    "source_files": [],
                    "tier": 3,
                }
            )
        )
        # Create target dirs
        (tmp_path / "src").mkdir(exist_ok=True)
        (tmp_path / "python" / "rust_accelerators").mkdir(parents=True, exist_ok=True)
        (tmp_path / "tests" / "unit").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / "migrations").mkdir(parents=True, exist_ok=True)
        return ws

    def test_promotes_files_to_correct_locations(self, tmp_path):
        self._setup_migration(tmp_path)
        promote_files(tmp_path, "pubsub")
        assert (tmp_path / "src" / "pubsub.rs").exists()
        assert (tmp_path / "python" / "rust_accelerators" / "pubsub.py").exists()
        assert (tmp_path / "tests" / "unit" / "test_pubsub.py").exists()
        assert (tmp_path / "docs" / "migrations" / "pubsub.md").exists()

    def test_removes_workspace_after_promotion(self, tmp_path):
        self._setup_migration(tmp_path)
        promote_files(tmp_path, "pubsub")
        assert not (tmp_path / "migrations" / "pubsub").exists()


class TestWirePermanently:
    def test_adds_mod_and_submodule_registration(self, tmp_path):
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
        wire_permanently(tmp_path, "pubsub")
        result = lib_rs.read_text()
        assert "mod pubsub;" in result
        assert "pubsub::register" in result
        # Should NOT have temporary markers
        assert "MIGRATION WIRE" not in result


class TestUpdateInitPy:
    def test_adds_module_import(self, tmp_path):
        init_py = tmp_path / "python" / "rust_accelerators" / "__init__.py"
        init_py.parent.mkdir(parents=True)
        init_py.write_text(
            '"""Rust-accelerated modules."""\n\n'
            "from rust_accelerators.metrics import is_accelerated\n"
        )
        update_init_py(tmp_path, "pubsub")
        result = init_py.read_text()
        assert "from rust_accelerators import pubsub" in result

    def test_idempotent(self, tmp_path):
        init_py = tmp_path / "python" / "rust_accelerators" / "__init__.py"
        init_py.parent.mkdir(parents=True)
        init_py.write_text('"""Rust-accelerated modules."""\n')
        update_init_py(tmp_path, "pubsub")
        update_init_py(tmp_path, "pubsub")
        result = init_py.read_text()
        assert result.count("import pubsub") == 1


class TestUpdateSupersedes:
    def test_adds_test_paths_to_supersedes(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.hummingbot.supersedes]\ntest_paths = []\n")
        update_supersedes(
            tmp_path,
            "pubsub",
            "hummingbot.core.pubsub",
            ["tests/core/test_pubsub.py"],
        )
        result = pyproject.read_text()
        assert "test_pubsub.py" in result

    def test_idempotent(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.hummingbot.supersedes]\ntest_paths = ["tests/core/test_pubsub.py"]\n'
        )
        update_supersedes(
            tmp_path,
            "pubsub",
            "hummingbot.core.pubsub",
            ["tests/core/test_pubsub.py"],
        )
        result = pyproject.read_text()
        assert result.count("test_pubsub.py") == 1

    def test_creates_section_if_missing(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\n')
        update_supersedes(
            tmp_path,
            "pubsub",
            "hummingbot.core.pubsub",
            ["tests/core/test_pubsub.py"],
        )
        result = pyproject.read_text()
        assert "supersedes" in result
        assert "test_pubsub.py" in result


class TestMergeCargoDeps:
    def test_merges_new_dependency(self, tmp_path):
        root_cargo = tmp_path / "Cargo.toml"
        root_cargo.write_text(
            '[package]\nname = "test"\nversion = "0.1.0"\nedition = "2021"\n\n'
            '[dependencies]\npyo3 = { version = "0.28", features = ["extension-module"] }\n'
        )
        migration_cargo = tmp_path / "migrations" / "pubsub" / "Cargo.toml"
        migration_cargo.parent.mkdir(parents=True)
        migration_cargo.write_text(
            '[package]\nname = "hb-rust-pubsub"\nversion = "0.1.0"\nedition = "2021"\n\n'
            '[dependencies]\npyo3 = { version = "0.28", features = ["extension-module"] }\n'
            'tokio = { version = "1", features = ["full"] }\n'
        )
        merge_cargo_dependencies(tmp_path, "pubsub")
        result = root_cargo.read_text()
        assert "tokio" in result

    def test_skips_existing_dependencies(self, tmp_path):
        root_cargo = tmp_path / "Cargo.toml"
        root_cargo.write_text(
            '[package]\nname = "test"\nversion = "0.1.0"\nedition = "2021"\n\n'
            '[dependencies]\npyo3 = { version = "0.28", features = ["extension-module"] }\n'
        )
        migration_cargo = tmp_path / "migrations" / "pubsub" / "Cargo.toml"
        migration_cargo.parent.mkdir(parents=True)
        migration_cargo.write_text(
            '[package]\nname = "hb-rust-pubsub"\nversion = "0.1.0"\nedition = "2021"\n\n'
            '[dependencies]\npyo3 = { version = "0.28", features = ["extension-module"] }\n'
        )
        merge_cargo_dependencies(tmp_path, "pubsub")
        result = root_cargo.read_text()
        # Should not duplicate pyo3
        assert result.count("pyo3") == 1

    def test_handles_missing_dependencies_section(self, tmp_path):
        root_cargo = tmp_path / "Cargo.toml"
        root_cargo.write_text('[package]\nname = "test"\nversion = "0.1.0"\nedition = "2021"\n')
        migration_cargo = tmp_path / "migrations" / "pubsub" / "Cargo.toml"
        migration_cargo.parent.mkdir(parents=True)
        migration_cargo.write_text(
            '[package]\nname = "hb-rust-pubsub"\nversion = "0.1.0"\nedition = "2021"\n\n'
            '[dependencies]\ntokio = { version = "1", features = ["full"] }\n'
        )
        merge_cargo_dependencies(tmp_path, "pubsub")
        result = root_cargo.read_text()
        assert "tokio" in result
