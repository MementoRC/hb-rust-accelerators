"""Tests for migration listing script."""

from __future__ import annotations

import json

from scripts.list_migrations import get_migrations_summary


class TestListMigrations:
    def test_empty_migrations_dir(self, tmp_path):
        result = get_migrations_summary(tmp_path / "migrations")
        assert result == []

    def test_no_migrations_dir(self, tmp_path):
        result = get_migrations_summary(tmp_path / "nonexistent")
        assert result == []

    def test_lists_migrations_with_status(self, tmp_path):
        m_dir = tmp_path / "migrations" / "pubsub"
        m_dir.mkdir(parents=True)
        (m_dir / "status.json").write_text(
            json.dumps(
                {
                    "issue_number": 20,
                    "module": "hummingbot.core.pubsub",
                    "status": "scaffolded",
                    "created": "2026-04-07",
                    "source_files": [],
                    "tier": 3,
                }
            )
        )
        result = get_migrations_summary(tmp_path / "migrations")
        assert len(result) == 1
        assert result[0]["name"] == "pubsub"
        assert result[0]["status"] == "scaffolded"
        assert result[0]["issue_number"] == 20

    def test_multiple_migrations(self, tmp_path):
        for name, status in [("pubsub", "in_progress"), ("tracker", "scaffolded")]:
            m_dir = tmp_path / "migrations" / name
            m_dir.mkdir(parents=True)
            (m_dir / "status.json").write_text(
                json.dumps(
                    {
                        "issue_number": 20,
                        "module": f"hummingbot.core.{name}",
                        "status": status,
                        "created": "2026-04-07",
                        "source_files": [],
                        "tier": 3,
                    }
                )
            )
        result = get_migrations_summary(tmp_path / "migrations")
        assert len(result) == 2
