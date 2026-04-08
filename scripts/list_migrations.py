"""List all migration workspaces and their status."""

from __future__ import annotations

import sys
from pathlib import Path

from scripts.migration_config import PROJECT_ROOT, read_status


def get_migrations_summary(migrations_dir: Path) -> list[dict]:
    """Get summary of all migration workspaces."""
    if not migrations_dir.is_dir():
        return []

    results = []
    for child in sorted(migrations_dir.iterdir()):
        status_file = child / "status.json"
        if child.is_dir() and status_file.exists():
            status = read_status(child)
            results.append({
                "name": child.name,
                "module": status.module,
                "status": status.status,
                "issue_number": status.issue_number,
                "tier": status.tier,
                "created": status.created,
            })
    return results


def print_dashboard(migrations_dir: Path) -> None:
    """Print a formatted dashboard of all migrations."""
    summaries = get_migrations_summary(migrations_dir)
    if not summaries:
        print("No migrations found.")
        return

    print(f"{'Name':<20} {'Module':<35} {'Status':<15} {'Issue':<8} {'Tier':<5} {'Created'}")
    print("-" * 100)
    for s in summaries:
        print(
            f"{s['name']:<20} {s['module']:<35} {s['status']:<15} "
            f"#{s['issue_number']:<7} T{s['tier']:<4} {s['created']}"
        )


if __name__ == "__main__":
    migrations_dir = PROJECT_ROOT / "migrations"
    if len(sys.argv) > 1:
        migrations_dir = Path(sys.argv[1])
    print_dashboard(migrations_dir)
