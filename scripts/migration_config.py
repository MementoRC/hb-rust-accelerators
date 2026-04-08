"""Shared configuration for migration tooling."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_CHECKOUT = "../../../"
DEFAULT_ISSUE_REPO = "MementoRC/hummingbot"


@dataclass
class MigrationConfig:
    source_checkout: str = DEFAULT_SOURCE_CHECKOUT
    issue_repo: str = DEFAULT_ISSUE_REPO

    def module_dir_name(
        self, module_path: str, migrations_root: Path | None = None
    ) -> str:
        """Derive directory name from module path, handling conflicts."""
        last_segment = module_path.rsplit(".", 1)[-1]
        if migrations_root is None:
            return last_segment

        existing_dir = migrations_root / last_segment
        if existing_dir.exists():
            status_file = existing_dir / "status.json"
            if status_file.exists():
                with open(status_file) as f:
                    existing = json.load(f)
                if existing.get("module") != module_path:
                    parts = module_path.rsplit(".", 2)
                    if len(parts) >= 2:
                        return f"{parts[-2]}_{parts[-1]}"
        return last_segment


@dataclass
class MigrationStatus:
    issue_number: int
    module: str
    status: str
    created: str
    source_files: list[str] = field(default_factory=list)
    tier: int = 3

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> MigrationStatus:
        return cls(**data)


def get_migration_config(pyproject_path: Path | None = None) -> MigrationConfig:
    """Load migration config from pyproject.toml."""
    if pyproject_path is None:
        pyproject_path = PROJECT_ROOT / "pyproject.toml"

    if not pyproject_path.exists():
        return MigrationConfig()

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    migration_section = (
        data.get("tool", {}).get("hummingbot", {}).get("migration", {})
    )
    return MigrationConfig(
        source_checkout=migration_section.get("source_checkout", DEFAULT_SOURCE_CHECKOUT),
        issue_repo=migration_section.get("issue_repo", DEFAULT_ISSUE_REPO),
    )


def resolve_source_checkout(pyproject_path: Path | None = None) -> Path:
    """Resolve the hummingbot source checkout path."""
    env_path = os.environ.get("HUMMINGBOT_SOURCE_PATH")
    if env_path:
        resolved = Path(env_path).resolve()
    else:
        if pyproject_path is None:
            pyproject_path = PROJECT_ROOT / "pyproject.toml"
        config = get_migration_config(pyproject_path)
        resolved = (pyproject_path.parent / config.source_checkout).resolve()

    if not (resolved / "hummingbot").is_dir():
        raise FileNotFoundError(
            f"No hummingbot/ directory found at {resolved}. "
            f"Set HUMMINGBOT_SOURCE_PATH or update [tool.hummingbot.migration] "
            f"source_checkout in pyproject.toml."
        )
    return resolved


def read_status(migration_dir: Path) -> MigrationStatus:
    """Read status.json from a migration workspace."""
    with open(migration_dir / "status.json") as f:
        return MigrationStatus.from_dict(json.load(f))


def write_status(migration_dir: Path, status: MigrationStatus) -> None:
    """Write status.json to a migration workspace."""
    with open(migration_dir / "status.json", "w") as f:
        json.dump(status.to_dict(), f, indent=2)
        f.write("\n")
