"""Tests for migration configuration module."""

from __future__ import annotations

import pytest

from scripts.migration_config import (
    MigrationConfig,
    MigrationStatus,
    get_migration_config,
    read_status,
    resolve_source_checkout,
    write_status,
)


class TestMigrationConfig:
    def test_load_from_pyproject(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.hummingbot.migration]\n"
            'source_checkout = "../../../"\n'
            'issue_repo = "MementoRC/hummingbot"\n'
        )
        config = get_migration_config(pyproject)
        assert config.source_checkout == "../../../"
        assert config.issue_repo == "MementoRC/hummingbot"

    def test_load_defaults_when_section_missing(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")
        config = get_migration_config(pyproject)
        assert config.source_checkout == "../../../"
        assert config.issue_repo == "MementoRC/hummingbot"


class TestResolveSourceCheckout:
    def test_env_var_takes_precedence(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HUMMINGBOT_SOURCE_PATH", str(tmp_path))
        (tmp_path / "hummingbot").mkdir()
        result = resolve_source_checkout(tmp_path / "pyproject.toml")
        assert result == tmp_path

    def test_pyproject_relative_path(self, tmp_path):
        project_root = tmp_path / "sub-packages" / "rust-accelerators"
        project_root.mkdir(parents=True)
        hb_root = tmp_path
        (hb_root / "hummingbot").mkdir()
        pyproject = project_root / "pyproject.toml"
        pyproject.write_text('[tool.hummingbot.migration]\nsource_checkout = "../../"\n')
        result = resolve_source_checkout(pyproject)
        assert result == hb_root

    def test_invalid_path_raises(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.hummingbot.migration]\nsource_checkout = "/nonexistent/path"\n')
        with pytest.raises(FileNotFoundError, match="hummingbot"):
            resolve_source_checkout(pyproject)


class TestMigrationStatus:
    def test_write_and_read_status(self, tmp_path):
        status = MigrationStatus(
            issue_number=20,
            module="hummingbot.core.pubsub",
            status="scaffolded",
            created="2026-04-07",
            source_files=["hummingbot/core/pubsub.pyx"],
            tier=3,
        )
        write_status(tmp_path, status)
        assert (tmp_path / "status.json").exists()
        loaded = read_status(tmp_path)
        assert loaded.issue_number == 20
        assert loaded.module == "hummingbot.core.pubsub"
        assert loaded.status == "scaffolded"

    def test_update_status(self, tmp_path):
        status = MigrationStatus(
            issue_number=20,
            module="hummingbot.core.pubsub",
            status="scaffolded",
            created="2026-04-07",
            source_files=[],
            tier=3,
        )
        write_status(tmp_path, status)
        loaded = read_status(tmp_path)
        loaded.status = "in_progress"
        write_status(tmp_path, loaded)
        reloaded = read_status(tmp_path)
        assert reloaded.status == "in_progress"


class TestModuleNaming:
    def test_simple_name(self):
        config = MigrationConfig()
        assert config.module_dir_name("hummingbot.core.pubsub") == "pubsub"

    def test_conflict_detection(self, tmp_path):
        config = MigrationConfig()
        migrations_dir = tmp_path / "migrations" / "pubsub"
        migrations_dir.mkdir(parents=True)
        existing_status = MigrationStatus(
            issue_number=10,
            module="hummingbot.other.pubsub",
            status="scaffolded",
            created="2026-04-07",
            source_files=[],
            tier=3,
        )
        write_status(migrations_dir, existing_status)
        name = config.module_dir_name(
            "hummingbot.core.pubsub", migrations_root=tmp_path / "migrations"
        )
        assert name == "core_pubsub"
