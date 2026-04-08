"""Tests for migration scaffold script."""

from __future__ import annotations

import json

import pytest

from scripts.scaffold_migration import scaffold_workspace


class TestScaffoldWorkspace:
    def test_creates_directory_structure(self, tmp_path):
        scaffold_workspace(
            module_name="pubsub",
            module_path="hummingbot.core.pubsub",
            issue_number=20,
            source_files=["hummingbot/core/pubsub.pyx"],
            tier=3,
            project_root=tmp_path,
        )
        ws = tmp_path / "migrations" / "pubsub"
        assert ws.is_dir()
        assert (ws / "Cargo.toml").exists()
        assert (ws / "src" / "lib.rs").exists()
        assert (ws / "python" / "pubsub.py").exists()
        assert (ws / "tests" / "test_pubsub.py").exists()
        assert (ws / "status.json").exists()
        assert (ws / "analysis.md").exists()

    def test_creates_valid_cargo_toml(self, tmp_path):
        scaffold_workspace(
            module_name="pubsub",
            module_path="hummingbot.core.pubsub",
            issue_number=20,
            source_files=[],
            tier=3,
            project_root=tmp_path,
        )
        cargo = (tmp_path / "migrations" / "pubsub" / "Cargo.toml").read_text()
        assert "[package]" in cargo
        assert 'name = "hb-rust-pubsub"' in cargo
        assert "pyo3" in cargo

    def test_creates_status_json(self, tmp_path):
        scaffold_workspace(
            module_name="pubsub",
            module_path="hummingbot.core.pubsub",
            issue_number=20,
            source_files=["hummingbot/core/pubsub.pyx"],
            tier=3,
            project_root=tmp_path,
        )
        status = json.loads((tmp_path / "migrations" / "pubsub" / "status.json").read_text())
        assert status["issue_number"] == 20
        assert status["status"] == "scaffolded"
        assert status["module"] == "hummingbot.core.pubsub"

    def test_lib_rs_has_register_function(self, tmp_path):
        scaffold_workspace(
            module_name="pubsub",
            module_path="hummingbot.core.pubsub",
            issue_number=20,
            source_files=[],
            tier=3,
            project_root=tmp_path,
        )
        lib_rs = (tmp_path / "migrations" / "pubsub" / "src" / "lib.rs").read_text()
        assert "pub fn register" in lib_rs
        assert "PyModule" in lib_rs

    def test_python_wrapper_has_module_name(self, tmp_path):
        scaffold_workspace(
            module_name="pubsub",
            module_path="hummingbot.core.pubsub",
            issue_number=20,
            source_files=[],
            tier=3,
            project_root=tmp_path,
        )
        wrapper = (tmp_path / "migrations" / "pubsub" / "python" / "pubsub.py").read_text()
        assert "pubsub" in wrapper

    def test_analysis_md_has_context_header(self, tmp_path):
        scaffold_workspace(
            module_name="pubsub",
            module_path="hummingbot.core.pubsub",
            issue_number=20,
            source_files=[],
            tier=3,
            project_root=tmp_path,
        )
        analysis = (tmp_path / "migrations" / "pubsub" / "analysis.md").read_text()
        assert "Implementation target: Claude Code session" in analysis

    def test_updates_root_cargo_workspace(self, tmp_path):
        root_cargo = tmp_path / "Cargo.toml"
        root_cargo.write_text(
            '[package]\nname = "hb-rust-accelerators"\nversion = "0.1.0"\n'
            'edition = "2021"\n\n[workspace]\nmembers = ["."]\n'
        )
        scaffold_workspace(
            module_name="pubsub",
            module_path="hummingbot.core.pubsub",
            issue_number=20,
            source_files=[],
            tier=3,
            project_root=tmp_path,
        )
        cargo_text = root_cargo.read_text()
        assert "migrations/pubsub" in cargo_text

    def test_refuses_to_overwrite_existing(self, tmp_path):
        scaffold_workspace(
            module_name="pubsub",
            module_path="hummingbot.core.pubsub",
            issue_number=20,
            source_files=[],
            tier=3,
            project_root=tmp_path,
        )
        with pytest.raises(FileExistsError):
            scaffold_workspace(
                module_name="pubsub",
                module_path="hummingbot.core.pubsub",
                issue_number=20,
                source_files=[],
                tier=3,
                project_root=tmp_path,
            )
