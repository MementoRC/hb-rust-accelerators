# Rust Migration Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tooling to rust-accelerators that scaffolds, develops, tests, and integrates Rust migrations of Cython/C++ hummingbot modules.

**Architecture:** Three scripts (`scaffold_migration.py`, `test_migration.py`, `integrate_module.py`) + a `list_migrations.py` dashboard, backed by a shared `migration_config.py` module for config/status. A Claude Code skill (`/migrate-module`) dispatches a domain agent that calls the scaffold script and adds intelligent content. A Cargo workspace structure supports parallel migrations.

**Tech Stack:** Python 3.10+, PyO3/maturin (Rust), toml (stdlib in 3.11+, tomli fallback), pytest, pixi tasks, Claude Code skill/agent

**Spec:** `docs/superpowers/specs/2026-04-07-rust-migration-factory-design.md`

---

## File Map

### New Files — Scripts

| File | Responsibility |
|------|---------------|
| `scripts/migration_config.py` | Shared config: read `[tool.hummingbot.migration]` from pyproject.toml, resolve source checkout path, read/write `status.json`, naming conflict detection |
| `scripts/scaffold_migration.py` | Create migration workspace directory structure, boilerplate Cargo.toml, empty files, update root Cargo.toml workspace members |
| `scripts/test_migration.py` | Wire migration module into `src/lib.rs`, run `maturin develop`, run pytest, unwire, update status.json |
| `scripts/integrate_module.py` | Promote files, wire permanently into lib.rs, update __init__.py, merge Cargo deps, update supersedes, archive |
| `scripts/list_migrations.py` | Read all `migrations/*/status.json`, print dashboard table |

### New Files — Templates

| File | Responsibility |
|------|---------------|
| `scripts/templates/migration_cargo.toml.tmpl` | Cargo.toml template for new migration workspace members |
| `scripts/templates/migration_lib.rs.tmpl` | Minimal `pub fn register()` scaffold for Rust module |
| `scripts/templates/migration_wrapper.py.tmpl` | Python wrapper template (fallback variant) |
| `scripts/templates/migration_wrapper_rust_only.py.tmpl` | Python wrapper template (Rust-only variant) |
| `scripts/templates/migration_test.py.tmpl` | Test file template |

### New Files — Tests

| File | Responsibility |
|------|---------------|
| `tests/unit/test_migration_config.py` | Tests for config loading, path resolution, status management, naming |
| `tests/unit/test_scaffold_migration.py` | Tests for scaffold script: directory creation, Cargo.toml update, conflict detection |
| `tests/unit/test_test_migration.py` | Tests for wire/unwire logic and status transitions |
| `tests/unit/test_integrate_module.py` | Tests for file promotion, lib.rs modification, dependency merge |
| `tests/unit/test_list_migrations.py` | Tests for dashboard output |

### New Files — Skill & Agent

| File | Responsibility |
|------|---------------|
| `~/.claude/skills/migrate-module.md` | Claude Code skill: primes context, dispatches agent |
| `~/.claude/agents/domain/rust-migration-scaffolder.md` | Domain agent: fetches issue, reads source, calls scaffold script, generates analysis.md |

### Modified Files

| File | Change |
|------|--------|
| `pyproject.toml` | Add `[tool.hummingbot.migration]` config, add pixi tasks, add `tomli` dependency, add `pythonpath = ["."]` to pytest config |
| `Cargo.toml` | Add `[workspace]` section (initially empty members list) |

---

## Task 1: Migration Config Module

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/migration_config.py`
- Test: `tests/unit/test_migration_config.py`

- [ ] **Step 1: Create scripts package**

```python
# scripts/__init__.py
# (empty)
```

- [ ] **Step 2: Write failing tests for config loading**

```python
# tests/unit/test_migration_config.py
"""Tests for migration configuration module."""

from __future__ import annotations

import json
from pathlib import Path

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
            '[tool.hummingbot.migration]\n'
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
        pyproject.write_text(
            '[tool.hummingbot.migration]\n'
            'source_checkout = "../../"\n'
        )
        result = resolve_source_checkout(pyproject)
        assert result == hb_root

    def test_invalid_path_raises(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.hummingbot.migration]\n'
            'source_checkout = "/nonexistent/path"\n'
        )
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pixi run test-unit -- tests/unit/test_migration_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts'`

- [ ] **Step 4: Implement migration_config.py**

```python
# scripts/migration_config.py
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
                    # Conflict: use longer name
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
    """Resolve the hummingbot source checkout path.

    Precedence: HUMMINGBOT_SOURCE_PATH env var > pyproject.toml config.
    """
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pixi run test-unit -- tests/unit/test_migration_config.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```
git add scripts/__init__.py scripts/migration_config.py tests/unit/test_migration_config.py
git commit -m "feat: add migration config module with status tracking and naming"
```

---

## Task 2: Scaffold Migration Script + Templates

**Files:**
- Create: `scripts/scaffold_migration.py`
- Create: `scripts/templates/migration_cargo.toml.tmpl`
- Create: `scripts/templates/migration_lib.rs.tmpl`
- Create: `scripts/templates/migration_wrapper.py.tmpl`
- Create: `scripts/templates/migration_wrapper_rust_only.py.tmpl`
- Create: `scripts/templates/migration_test.py.tmpl`
- Modify: `Cargo.toml` — add `[workspace]` section
- Test: `tests/unit/test_scaffold_migration.py`

- [ ] **Step 1: Create template files**

`scripts/templates/migration_cargo.toml.tmpl`:
```toml
[package]
name = "hb-rust-{module_name}"
version = "0.1.0"
edition = "2021"
license = "Apache-2.0"

[lib]
name = "{module_name}"
path = "src/lib.rs"
# rlib only — this crate is compiled into the root cdylib via maturin,
# not built as a standalone extension module.
crate-type = ["rlib"]

[dependencies]
# No extension-module feature — this workspace member is compiled as rlib
# into the root _core cdylib. Only the root crate needs extension-module.
pyo3 = "0.28"
```

`scripts/templates/migration_lib.rs.tmpl`:
```rust
use pyo3::prelude::*;

/// Register {module_name} types and functions on the given PyModule.
///
/// Called by the root _core module at integration time:
///   let m = PyModule::new(py, "{module_name}")?;
///   {module_name}::register(m.as_borrowed())?;
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {{
    // TODO: Register your #[pyclass] and #[pyfunction] items here
    // Example:
    //   m.add_class::<MyClass>()?;
    //   m.add_function(wrap_pyfunction!(my_function, m)?)?;
    Ok(())
}}
```

`scripts/templates/migration_wrapper.py.tmpl`:
```python
"""{module_path} — Rust-accelerated with Python fallback."""

from __future__ import annotations

try:
    from rust_accelerators._core.{module_name} import *  # noqa: F401,F403

    _ACCELERATED = True
except ImportError:
    _ACCELERATED = False
    # TODO: Add pure-Python fallback implementations here


def is_accelerated() -> bool:
    """Return True if Rust acceleration is available for {module_name}."""
    return _ACCELERATED
```

`scripts/templates/migration_wrapper_rust_only.py.tmpl`:
```python
"""{module_path} — Rust implementation (no Python fallback).

This module requires the Rust extension to be built. Run:
    pixi run rust-build
"""

from __future__ import annotations

from rust_accelerators._core.{module_name} import *  # noqa: F401,F403


def is_accelerated() -> bool:
    """Return True (always — this module requires Rust)."""
    return True
```

`scripts/templates/migration_test.py.tmpl`:
```python
"""Tests for {module_name} migration."""

from __future__ import annotations

import pytest


class Test{class_name}:
    """Test the {module_name} module API."""

    # TODO: Add tests based on the original hummingbot test suite.
    # See analysis.md for the original API surface and test cases.

    def test_placeholder(self):
        """Remove this once real tests are added."""
        pytest.skip("Scaffold placeholder — implement tests from analysis.md")
```

- [ ] **Step 2: Write failing tests for scaffold script**

```python
# tests/unit/test_scaffold_migration.py
"""Tests for migration scaffold script."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.scaffold_migration import scaffold_workspace


class TestScaffoldWorkspace:
    def test_creates_directory_structure(self, tmp_path):
        result = scaffold_workspace(
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
        status = json.loads(
            (tmp_path / "migrations" / "pubsub" / "status.json").read_text()
        )
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pixi run test-unit -- tests/unit/test_scaffold_migration.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.scaffold_migration'` (templates exist, but implementation does not)

- [ ] **Step 4: Implement scaffold_migration.py**

```python
# scripts/scaffold_migration.py
"""Create a migration workspace for a hummingbot module."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from scripts.migration_config import MigrationStatus, write_status

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _read_template(name: str) -> str:
    return (TEMPLATES_DIR / name).read_text()


def _update_cargo_workspace(project_root: Path, member_path: str) -> None:
    """Add a member to the [workspace] section in root Cargo.toml."""
    cargo_path = project_root / "Cargo.toml"
    text = cargo_path.read_text()

    # Find members list and add new member
    pattern = r'(members\s*=\s*\[)(.*?)(\])'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        members_content = match.group(2)
        if member_path not in members_content:
            # Add new member before closing bracket
            if members_content.strip():
                new_members = f'{members_content.rstrip()}, "{member_path}"'
            else:
                new_members = f'"{member_path}"'
            text = text[: match.start(2)] + new_members + text[match.end(2) :]
            cargo_path.write_text(text)


def scaffold_workspace(
    module_name: str,
    module_path: str,
    issue_number: int,
    source_files: list[str],
    tier: int,
    project_root: Path | None = None,
) -> Path:
    """Create a migration workspace directory with scaffold files.

    Returns the path to the created workspace.
    """
    if project_root is None:
        project_root = PROJECT_ROOT

    ws = project_root / "migrations" / module_name
    if ws.exists():
        raise FileExistsError(f"Migration workspace already exists: {ws}")

    # Create directory structure
    (ws / "src").mkdir(parents=True)
    (ws / "python").mkdir()
    (ws / "tests").mkdir()

    # Class name for templates
    class_name = "".join(part.capitalize() for part in module_name.split("_"))

    # Write Cargo.toml from template
    cargo_tmpl = _read_template("migration_cargo.toml.tmpl")
    (ws / "Cargo.toml").write_text(
        cargo_tmpl.format(module_name=module_name)
    )

    # Write src/lib.rs from template
    lib_tmpl = _read_template("migration_lib.rs.tmpl")
    (ws / "src" / "lib.rs").write_text(
        lib_tmpl.format(module_name=module_name)
    )

    # Write Python wrapper (default: fallback variant; agent may replace with rust-only)
    wrapper_tmpl = _read_template("migration_wrapper.py.tmpl")
    (ws / "python" / f"{module_name}.py").write_text(
        wrapper_tmpl.format(module_name=module_name, module_path=module_path)
    )

    # Write test scaffold
    test_tmpl = _read_template("migration_test.py.tmpl")
    (ws / "tests" / f"test_{module_name}.py").write_text(
        test_tmpl.format(module_name=module_name, class_name=class_name)
    )

    # Write analysis.md scaffold
    (ws / "analysis.md").write_text(
        f"Implementation target: Claude Code session in rust-accelerators.\n"
        f"Follow the metrics module pattern in src/lib.rs for PyO3 conventions.\n\n"
        f"# {module_path} Migration Analysis\n\n"
        f"**Issue**: #{issue_number}\n"
        f"**Tier**: {tier}\n"
        f"**Source files**: {', '.join(source_files) or 'none listed'}\n\n"
        f"## Original API Surface\n\n"
        f"TODO: Agent will populate from source analysis.\n\n"
        f"## Data Structures\n\n"
        f"TODO: Agent will populate C++ → Rust mapping.\n\n"
        f"## Suggested Crate Dependencies\n\n"
        f"TODO: Agent will suggest based on source analysis.\n\n"
        f"## Fallback Feasibility\n\n"
        f"TODO: Agent will assess if pure-Python fallback is practical.\n\n"
        f"## Existing Tests\n\n"
        f"TODO: Agent will extract from hummingbot test suite.\n\n"
        f"## Known Complexity\n\n"
        f"TODO: Agent will flag tricky patterns.\n"
    )

    # Write status.json
    status = MigrationStatus(
        issue_number=issue_number,
        module=module_path,
        status="scaffolded",
        created=str(date.today()),
        source_files=source_files,
        tier=tier,
    )
    write_status(ws, status)

    # Update root Cargo.toml workspace members
    cargo_path = project_root / "Cargo.toml"
    if cargo_path.exists() and "[workspace]" in cargo_path.read_text():
        _update_cargo_workspace(project_root, f"migrations/{module_name}")

    return ws


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: scaffold_migration.py <module_name> <module_path> [issue_number] [tier]")
        sys.exit(1)

    name = sys.argv[1]
    path = sys.argv[2]
    issue = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    tier = int(sys.argv[4]) if len(sys.argv) > 4 else 3

    result = scaffold_workspace(name, path, issue, [], tier)
    print(f"Created migration workspace: {result}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pixi run test-unit -- tests/unit/test_scaffold_migration.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```
git add scripts/scaffold_migration.py scripts/templates/ tests/unit/test_scaffold_migration.py
git commit -m "feat: add scaffold migration script with templates"
```

---

## Task 3: Add Cargo Workspace + pyproject.toml Config

**Files:**
- Modify: `Cargo.toml` — add `[workspace]` section
- Modify: `pyproject.toml` — add `[tool.hummingbot.migration]` config, pixi tasks, tomli dep

- [ ] **Step 1: Update Cargo.toml**

Add workspace section after `[dependencies]`:

```toml
[workspace]
members = ["."]
```

- [ ] **Step 2: Verify Rust build still works**

Run: `pixi run rust-build-debug`
Expected: builds successfully

- [ ] **Step 3: Add migration config to pyproject.toml**

Add after `[tool.hummingbot.supersedes]` section:

```toml
[tool.hummingbot.migration]
source_checkout = "../../../"
issue_repo = "MementoRC/hummingbot"
```

- [ ] **Step 4: Add tomli to dependencies (Python 3.10 support)**

In `[tool.pixi.dependencies]` (base, not just dev/ci):
```toml
tomli = "*"
```

- [ ] **Step 5: Add pythonpath to pytest config**

In `[tool.pytest.ini_options]`, add:
```toml
pythonpath = ["."]
```

This makes `scripts/` importable in tests without sys.path hacks.

- [ ] **Step 6: Add pixi tasks for migration workflow**

Add to `[tool.pixi.tasks]`:

```toml
scaffold-migration = "python scripts/scaffold_migration.py"
list-migrations = "python scripts/list_migrations.py"
```

Note: `test-migration` and `integrate-module` tasks are added in their respective tasks below.

- [ ] **Step 7: Run full test suite to verify nothing broke**

Run: `pixi run test`
Expected: all existing tests PASS

- [ ] **Step 8: Commit**

```
git add Cargo.toml pyproject.toml
git commit -m "feat: add Cargo workspace and migration config to pyproject.toml"
```

---

## Task 4: List Migrations Script

**Files:**
- Create: `scripts/list_migrations.py`
- Test: `tests/unit/test_list_migrations.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_list_migrations.py
"""Tests for migration listing script."""

from __future__ import annotations

import json
from pathlib import Path

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
        (m_dir / "status.json").write_text(json.dumps({
            "issue_number": 20,
            "module": "hummingbot.core.pubsub",
            "status": "scaffolded",
            "created": "2026-04-07",
            "source_files": [],
            "tier": 3,
        }))
        result = get_migrations_summary(tmp_path / "migrations")
        assert len(result) == 1
        assert result[0]["name"] == "pubsub"
        assert result[0]["status"] == "scaffolded"
        assert result[0]["issue_number"] == 20

    def test_multiple_migrations(self, tmp_path):
        for name, status in [("pubsub", "in_progress"), ("tracker", "scaffolded")]:
            m_dir = tmp_path / "migrations" / name
            m_dir.mkdir(parents=True)
            (m_dir / "status.json").write_text(json.dumps({
                "issue_number": 20,
                "module": f"hummingbot.core.{name}",
                "status": status,
                "created": "2026-04-07",
                "source_files": [],
                "tier": 3,
            }))
        result = get_migrations_summary(tmp_path / "migrations")
        assert len(result) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test-unit -- tests/unit/test_list_migrations.py -v`
Expected: FAIL

- [ ] **Step 3: Implement list_migrations.py**

```python
# scripts/list_migrations.py
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

    # Header
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pixi run test-unit -- tests/unit/test_list_migrations.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```
git add scripts/list_migrations.py tests/unit/test_list_migrations.py
git commit -m "feat: add list-migrations dashboard script"
```

---

## Task 5: Test Migration Script (Wire/Build/Test/Unwire)

**Files:**
- Create: `scripts/test_migration.py`
- Test: `tests/unit/test_test_migration.py`

- [ ] **Step 1: Write failing tests for wire/unwire logic**

```python
# tests/unit/test_test_migration.py
"""Tests for test-migration wire/unwire and status transitions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.test_migration import (
    unwire_module,
    wire_module,
)
from scripts.migration_config import MigrationStatus, read_status, write_status


class TestWireModule:
    def test_wire_adds_mod_and_submodule(self, tmp_path):
        lib_rs = tmp_path / "src" / "lib.rs"
        lib_rs.parent.mkdir(parents=True)
        lib_rs.write_text(
            'use pyo3::prelude::*;\n\n'
            '#[pymodule]\n'
            'fn _core(m: &Bound<\'_, PyModule>) -> PyResult<()> {\n'
            '    m.add_function(wrap_pyfunction!(calculate_max_drawdown, m)?)?;\n'
            '    Ok(())\n'
            '}\n'
        )
        wire_module(tmp_path, "pubsub", tmp_path / "migrations" / "pubsub" / "src" / "lib.rs")
        result = lib_rs.read_text()
        assert '#[path = "' in result or "mod pubsub;" in result
        assert "pubsub::register" in result

    def test_unwire_removes_additions(self, tmp_path):
        lib_rs = tmp_path / "src" / "lib.rs"
        lib_rs.parent.mkdir(parents=True)
        original = (
            'use pyo3::prelude::*;\n\n'
            '#[pymodule]\n'
            'fn _core(m: &Bound<\'_, PyModule>) -> PyResult<()> {\n'
            '    m.add_function(wrap_pyfunction!(calculate_max_drawdown, m)?)?;\n'
            '    Ok(())\n'
            '}\n'
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
            'use pyo3::prelude::*;\n\n'
            '#[pymodule]\n'
            'fn _core(m: &Bound<\'_, PyModule>) -> PyResult<()> {\n'
            '    Ok(())\n'
            '}\n'
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
            'use pyo3::prelude::*;\n\n'
            '#[pymodule]\n'
            'fn _core(m: &Bound<\'_, PyModule>) -> PyResult<()> {\n'
            '    Ok(())\n'
            '}\n'
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
        write_status(m_dir, MigrationStatus(
            issue_number=20, module="hummingbot.core.pubsub",
            status="scaffolded", created="2026-04-07",
            source_files=[], tier=3,
        ))

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test-unit -- tests/unit/test_test_migration.py -v`
Expected: FAIL

- [ ] **Step 3: Implement test_migration.py**

```python
# scripts/test_migration.py
"""Wire a migration module into the main crate, build, test, unwire."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from scripts.migration_config import PROJECT_ROOT, read_status, write_status

# Markers for wire/unwire
WIRE_START = "// --- MIGRATION WIRE START: {module} ---"
WIRE_END = "// --- MIGRATION WIRE END: {module} ---"
WIRE_REG_START = "    // --- MIGRATION REG START: {module} ---"
WIRE_REG_END = "    // --- MIGRATION REG END: {module} ---"


def wire_module(project_root: Path, module_name: str, module_src: Path) -> None:
    """Temporarily wire a migration module into src/lib.rs for building."""
    lib_rs = project_root / "src" / "lib.rs"
    text = lib_rs.read_text()

    # Add mod declaration with path attribute (before #[pymodule])
    rel_path = module_src.relative_to(project_root)
    mod_decl = (
        f'{WIRE_START.format(module=module_name)}\n'
        f'#[path = "{rel_path}"]\n'
        f'mod {module_name};\n'
        f'{WIRE_END.format(module=module_name)}\n'
    )

    # Insert mod declaration before #[pymodule]
    text = re.sub(
        r'(#\[pymodule\])',
        f'{mod_decl}\n\\1',
        text,
        count=1,
    )

    # Add submodule registration before Ok(())
    reg_code = (
        f'{WIRE_REG_START.format(module=module_name)}\n'
        f'    let {module_name}_module = PyModule::new(m.py(), "{module_name}")?;\n'
        f'    {module_name}::register({module_name}_module.as_borrowed())?;\n'
        f'    m.add_submodule(&{module_name}_module)?;\n'
        f'{WIRE_REG_END.format(module=module_name)}\n'
    )
    text = text.replace(
        '    Ok(())',
        f'{reg_code}    Ok(())',
        1,
    )

    lib_rs.write_text(text)


def unwire_module(project_root: Path, module_name: str) -> None:
    """Remove the temporary wiring for a migration module."""
    lib_rs = project_root / "src" / "lib.rs"
    text = lib_rs.read_text()

    # Remove mod declaration block (including the blank line after)
    mod_pattern = re.escape(WIRE_START.format(module=module_name)) + r'.*?' + re.escape(WIRE_END.format(module=module_name)) + r'\n*'
    text = re.sub(mod_pattern, '', text, flags=re.DOTALL)

    # Remove registration block
    reg_pattern = re.escape(WIRE_REG_START.format(module=module_name)) + r'.*?' + re.escape(WIRE_REG_END.format(module=module_name)) + r'\n'
    text = re.sub(reg_pattern, '', text, flags=re.DOTALL)

    lib_rs.write_text(text)


def update_status_for_run(migration_dir: Path, test_passed: bool) -> None:
    """Update status.json based on test results."""
    status = read_status(migration_dir)
    if status.status == "scaffolded":
        status.status = "in_progress"
    elif test_passed and status.status in ("in_progress", "tests_passing"):
        status.status = "tests_passing"
    elif not test_passed and status.status == "tests_passing":
        status.status = "in_progress"
    write_status(migration_dir, status)


def run_test_migration(module_name: str, project_root: Path | None = None) -> int:
    """Wire, build, test, unwire a migration module. Returns exit code."""
    if project_root is None:
        project_root = PROJECT_ROOT

    migration_dir = project_root / "migrations" / module_name
    if not migration_dir.is_dir():
        print(f"Error: Migration workspace not found: {migration_dir}")
        return 1

    # Recovery: if lib.rs is already wired (e.g. from a previous crash), unwire first
    lib_rs = project_root / "src" / "lib.rs"
    lib_rs_text = lib_rs.read_text()
    if f"MIGRATION WIRE START: {module_name}" in lib_rs_text:
        print(f"Warning: lib.rs already wired for {module_name}. Unwiring before proceeding...")
        unwire_module(project_root, module_name)

    module_src = migration_dir / "src" / "lib.rs"

    try:
        # Wire
        wire_module(project_root, module_name, module_src)

        # Build with maturin
        build_result = subprocess.run(
            ["pixi", "run", "rust-build-debug"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if build_result.returncode != 0:
            print(f"Build failed:\n{build_result.stderr}")
            update_status_for_run(migration_dir, test_passed=False)
            return build_result.returncode

        # Test
        test_result = subprocess.run(
            ["pixi", "run", "python", "-m", "pytest", f"migrations/{module_name}/tests/", "-v"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        print(test_result.stdout)
        if test_result.stderr:
            print(test_result.stderr)

        update_status_for_run(migration_dir, test_passed=(test_result.returncode == 0))
        return test_result.returncode

    finally:
        # Always unwire
        unwire_module(project_root, module_name)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: test_migration.py <module_name>")
        sys.exit(1)
    sys.exit(run_test_migration(sys.argv[1]))
```

- [ ] **Step 4: Add pixi task**

In `pyproject.toml` `[tool.pixi.tasks]`:
```toml
test-migration = "python scripts/test_migration.py"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pixi run test-unit -- tests/unit/test_test_migration.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```
git add scripts/test_migration.py tests/unit/test_test_migration.py pyproject.toml
git commit -m "feat: add test-migration script with wire/unwire and status transitions"
```

---

## Task 6: Integrate Module Script

**Files:**
- Create: `scripts/integrate_module.py`
- Test: `tests/unit/test_integrate_module.py`

- [ ] **Step 1: Write failing tests for integration logic**

```python
# tests/unit/test_integrate_module.py
"""Tests for module integration script."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
        (ws / "status.json").write_text(json.dumps({
            "issue_number": 20, "module": "hummingbot.core.pubsub",
            "status": "tests_passing", "created": "2026-04-07",
            "source_files": [], "tier": 3,
        }))
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
            'use pyo3::prelude::*;\n\n'
            '#[pymodule]\n'
            'fn _core(m: &Bound<\'_, PyModule>) -> PyResult<()> {\n'
            '    m.add_function(wrap_pyfunction!(calculate_max_drawdown, m)?)?;\n'
            '    Ok(())\n'
            '}\n'
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
            'from rust_accelerators.metrics import is_accelerated\n'
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
        pyproject.write_text(
            '[tool.hummingbot.supersedes]\n'
            'test_paths = []\n'
        )
        update_supersedes(
            tmp_path, "pubsub", "hummingbot.core.pubsub",
            ["tests/core/test_pubsub.py"],
        )
        result = pyproject.read_text()
        assert "test_pubsub.py" in result

    def test_idempotent(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.hummingbot.supersedes]\n'
            'test_paths = ["tests/core/test_pubsub.py"]\n'
        )
        update_supersedes(
            tmp_path, "pubsub", "hummingbot.core.pubsub",
            ["tests/core/test_pubsub.py"],
        )
        result = pyproject.read_text()
        assert result.count("test_pubsub.py") == 1

    def test_creates_section_if_missing(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\n')
        update_supersedes(
            tmp_path, "pubsub", "hummingbot.core.pubsub",
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
        root_cargo.write_text(
            '[package]\nname = "test"\nversion = "0.1.0"\nedition = "2021"\n'
        )
        migration_cargo = tmp_path / "migrations" / "pubsub" / "Cargo.toml"
        migration_cargo.parent.mkdir(parents=True)
        migration_cargo.write_text(
            '[package]\nname = "hb-rust-pubsub"\nversion = "0.1.0"\nedition = "2021"\n\n'
            '[dependencies]\ntokio = { version = "1", features = ["full"] }\n'
        )
        merge_cargo_dependencies(tmp_path, "pubsub")
        result = root_cargo.read_text()
        assert "tokio" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test-unit -- tests/unit/test_integrate_module.py -v`
Expected: FAIL

- [ ] **Step 3: Implement integrate_module.py**

```python
# scripts/integrate_module.py
"""Promote a completed migration into the main rust-accelerators package."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

from scripts.migration_config import PROJECT_ROOT, read_status, write_status


def promote_files(project_root: Path, module_name: str) -> None:
    """Move migration files to their permanent locations."""
    ws = project_root / "migrations" / module_name

    # Rust source
    shutil.copy2(ws / "src" / "lib.rs", project_root / "src" / f"{module_name}.rs")

    # Python wrapper
    shutil.copy2(
        ws / "python" / f"{module_name}.py",
        project_root / "python" / "rust_accelerators" / f"{module_name}.py",
    )

    # Tests
    shutil.copy2(
        ws / "tests" / f"test_{module_name}.py",
        project_root / "tests" / "unit" / f"test_{module_name}.py",
    )

    # Benchmarks (if exists)
    bench_src = ws / "tests" / f"bench_{module_name}.py"
    if bench_src.exists():
        shutil.copy2(
            bench_src,
            project_root / "tests" / "benchmarks" / f"bench_{module_name}.py",
        )

    # Archive analysis
    docs_dir = project_root / "docs" / "migrations"
    docs_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ws / "analysis.md", docs_dir / f"{module_name}.md")

    # Archive status
    status = read_status(ws)
    status.status = "integrated"
    write_status(docs_dir, status)

    # Remove workspace
    shutil.rmtree(ws)


def wire_permanently(project_root: Path, module_name: str) -> None:
    """Add permanent mod declaration and submodule registration to lib.rs."""
    lib_rs = project_root / "src" / "lib.rs"
    text = lib_rs.read_text()

    # Add mod declaration before #[pymodule]
    if f"mod {module_name};" not in text:
        text = re.sub(
            r'(#\[pymodule\])',
            f'mod {module_name};\n\n\\1',
            text,
            count=1,
        )

    # Add submodule registration before Ok(())
    if f"{module_name}::register" not in text:
        reg_code = (
            f'\n    let {module_name}_module = PyModule::new(m.py(), "{module_name}")?;\n'
            f'    {module_name}::register({module_name}_module.as_borrowed())?;\n'
            f'    m.add_submodule(&{module_name}_module)?;\n\n'
        )
        text = text.replace('    Ok(())', f'{reg_code}    Ok(())', 1)

    lib_rs.write_text(text)


def update_init_py(project_root: Path, module_name: str) -> None:
    """Add module-level import to __init__.py."""
    init_py = project_root / "python" / "rust_accelerators" / "__init__.py"
    text = init_py.read_text()
    import_line = f"from rust_accelerators import {module_name}  # noqa: F401"
    if import_line not in text and f"import {module_name}" not in text:
        text = text.rstrip() + f"\n\n{import_line}\n"
        init_py.write_text(text)


def merge_cargo_dependencies(project_root: Path, module_name: str) -> None:
    """Merge migration Cargo.toml dependencies into root Cargo.toml."""
    migration_cargo_path = project_root / "migrations" / module_name / "Cargo.toml"
    root_cargo_path = project_root / "Cargo.toml"

    with open(migration_cargo_path, "rb") as f:
        migration_data = tomllib.load(f)
    with open(root_cargo_path, "rb") as f:
        root_data = tomllib.load(f)

    root_deps = root_data.get("dependencies", {})
    migration_deps = migration_data.get("dependencies", {})

    # Find new deps to add
    new_deps = {}
    for dep_name, dep_spec in migration_deps.items():
        if dep_name not in root_deps:
            new_deps[dep_name] = dep_spec

    if not new_deps:
        return

    # Append new dependencies to root Cargo.toml
    root_text = root_cargo_path.read_text()
    dep_lines = []
    for dep_name, dep_spec in sorted(new_deps.items()):
        if isinstance(dep_spec, str):
            dep_lines.append(f'{dep_name} = "{dep_spec}"')
        elif isinstance(dep_spec, dict):
            parts = []
            for k, v in dep_spec.items():
                if isinstance(v, str):
                    parts.append(f'{k} = "{v}"')
                elif isinstance(v, list):
                    items = ", ".join(f'"{i}"' for i in v)
                    parts.append(f'{k} = [{items}]')
                elif isinstance(v, bool):
                    parts.append(f'{k} = {"true" if v else "false"}')
            dep_lines.append(f'{dep_name} = {{ {", ".join(parts)} }}')

    # Insert after last dependency line
    lines = root_text.split("\n")
    in_deps = False
    insert_idx = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == "[dependencies]":
            in_deps = True
        elif in_deps and (line.startswith("[") or line.strip() == ""):
            insert_idx = i
            break

    for dep_line in dep_lines:
        lines.insert(insert_idx, dep_line)
        insert_idx += 1
        print(f"  Added dependency: {dep_line}")

    root_cargo_path.write_text("\n".join(lines))


def remove_workspace_member(project_root: Path, module_name: str) -> None:
    """Remove migration from Cargo workspace members."""
    cargo_path = project_root / "Cargo.toml"
    text = cargo_path.read_text()
    member = f'"migrations/{module_name}"'
    text = text.replace(f", {member}", "").replace(f"{member}, ", "").replace(member, "")
    cargo_path.write_text(text)


def update_supersedes(
    project_root: Path,
    module_name: str,
    module_path: str,
    test_paths: list[str],
) -> None:
    """Add hummingbot test paths to [tool.hummingbot.supersedes] in pyproject.toml."""
    pyproject_path = project_root / "pyproject.toml"
    text = pyproject_path.read_text()

    # Parse current test_paths list from the supersedes section (simple line-based approach)
    # to avoid rewriting the entire file with a TOML writer.
    supersedes_header = "[tool.hummingbot.supersedes]"
    test_paths_key = "test_paths"

    new_paths = [p for p in test_paths if p not in text]
    if not new_paths:
        return

    if supersedes_header not in text:
        # Append a new section
        entries = "\n".join(f'    "{p}",' for p in new_paths)
        text = text.rstrip() + f"\n\n{supersedes_header}\n{test_paths_key} = [\n{entries}\n]\n"
    else:
        # Inject new paths into the existing test_paths list
        for path in new_paths:
            # Insert before the closing bracket of test_paths
            text = re.sub(
                r'(test_paths\s*=\s*\[)(.*?)(\])',
                lambda m: (
                    m.group(1) + m.group(2).rstrip() +
                    (", " if m.group(2).strip() else "") +
                    f'"{path}"' + m.group(3)
                ),
                text,
                flags=re.DOTALL,
            )

    pyproject_path.write_text(text)


def integrate_module(module_name: str, project_root: Path | None = None) -> int:
    """Full integration workflow. Returns 0 on success."""
    if project_root is None:
        project_root = PROJECT_ROOT

    migration_dir = project_root / "migrations" / module_name
    if not migration_dir.is_dir():
        print(f"Error: Migration workspace not found: {migration_dir}")
        return 1

    status = read_status(migration_dir)
    if status.status not in ("tests_passing", "in_progress"):
        print(f"Warning: Migration status is '{status.status}', expected 'tests_passing'")

    print(f"Integrating {module_name} ({status.module})...")

    # Merge Cargo deps before removing workspace
    print("Merging Cargo dependencies...")
    merge_cargo_dependencies(project_root, module_name)

    # Update supersedes list in pyproject.toml
    print("Updating supersedes list in pyproject.toml...")
    test_paths = [
        f"tests/{p.replace('.', '/')}.py"
        for p in status.source_files
        if p.endswith(".pyx")
    ]
    update_supersedes(project_root, module_name, status.module, test_paths)

    # Wire permanently into lib.rs
    print("Wiring into src/lib.rs...")
    wire_permanently(project_root, module_name)

    # Update __init__.py
    print("Updating __init__.py...")
    update_init_py(project_root, module_name)

    # Remove workspace member
    print("Removing workspace member...")
    remove_workspace_member(project_root, module_name)

    # Promote files (also removes workspace dir)
    print("Promoting files...")
    promote_files(project_root, module_name)

    # Run full test suite to verify integration
    print("Running post-integration tests...")
    test_result = subprocess.run(
        ["pixi", "run", "test"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    print(test_result.stdout)
    if test_result.returncode != 0:
        print(f"Post-integration tests FAILED:\n{test_result.stderr}")
        return test_result.returncode

    print(f"Integration complete and tests pass.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: integrate_module.py <module_name>")
        sys.exit(1)
    sys.exit(integrate_module(sys.argv[1]))
```

- [ ] **Step 4: Add pixi task**

In `pyproject.toml` `[tool.pixi.tasks]`:
```toml
integrate-module = "python scripts/integrate_module.py"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pixi run test-unit -- tests/unit/test_integrate_module.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```
git add scripts/integrate_module.py tests/unit/test_integrate_module.py pyproject.toml
git commit -m "feat: add integrate-module script for migration promotion"
```

---

## Task 7: Claude Code Skill + Domain Agent

**Files:**
- Create: `~/.claude/skills/migrate-module.md`
- Create: `~/.claude/agents/domain/rust-migration-scaffolder.md`

- [ ] **Step 1: Create the `/migrate-module` skill**

```markdown
# ~/.claude/skills/migrate-module.md
---
name: migrate-module
description: Scaffold a Rust migration workspace from a hummingbot GitHub issue. Dispatches rust-migration-scaffolder agent to fetch issue, analyze source, and create migrations/<module>/ workspace.
---

# Migrate Module

Scaffold a Rust migration workspace from a hummingbot migration issue.

## Usage

    /migrate-module <issue-number>

## What This Does

1. Dispatches the `rust-migration-scaffolder` agent
2. Agent fetches the issue from MementoRC/hummingbot
3. Agent reads the hummingbot source from local checkout
4. Agent creates `migrations/<module>/` workspace with:
   - Scaffolded Rust code (`src/lib.rs` with PyO3 signatures)
   - Python wrapper (`python/<module>.py`)
   - Test scaffold (`tests/test_<module>.py`)
   - Self-contained analysis doc (`analysis.md`)
   - Status tracking (`status.json`)
5. Returns summary of what was created and suggested approach

## After Scaffolding

Continue in a Claude Code session to implement the Rust module:
- Read `migrations/<module>/analysis.md` for full context
- Use `pixi run test-migration <module>` to build and test
- When tests pass, use `pixi run integrate-module <module>` to promote

## Dispatch

Spawn agent `rust-migration-scaffolder` with:
- `subagent_type`: `rust-migration-scaffolder`
- `model`: `sonnet`
- Issue number from arguments
- Project root: current working directory
```

- [ ] **Step 2: Create the `rust-migration-scaffolder` agent**

```markdown
# ~/.claude/agents/domain/rust-migration-scaffolder.md
---
name: rust-migration-scaffolder
description: Fetches a hummingbot migration issue, analyzes the source module, and scaffolds a Rust migration workspace in rust-accelerators with PyO3 signatures, Python wrapper, tests, and self-contained analysis doc.
model: sonnet
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - mcp__git__discover_tools
  - mcp__git__get_tool_spec
  - mcp__git__execute_tool
  - mcp__pixi-bash__execute_tool
  - mcp__pixi-bash__get_tool_spec
---

# Rust Migration Scaffolder

You scaffold Rust migration workspaces for hummingbot modules.

## Input

You receive:
- An issue number from MementoRC/hummingbot
- The project root path (rust-accelerators)

## Workflow

### 1. Fetch the Issue

Use GitHub MCP tools to fetch the issue:

    mcp__git__execute_tool("github_get_issue", {
        "repo_owner": "MementoRC",
        "repo_name": "hummingbot",
        "issue_number": <number>
    })

Extract from the issue body:
- Module path (e.g., `hummingbot.core.pubsub`)
- Source files (`.pyx`, `.pxd`, `.cpp`, `.h`)
- C++ dependencies
- API surface (function signatures)
- Tier

### 2. Read Hummingbot Source

Resolve the source checkout path from `pyproject.toml` `[tool.hummingbot.migration]`.
Read each source file listed in the issue using the Read tool.
Also search for existing tests: `Grep` for `test.*<module_name>` in the hummingbot test directory.

### 3. Run Scaffold Script

Use pixi to run the scaffold script:

    pixi run scaffold-migration <module_name> <module_path> <issue_number> <tier>

### 4. Fill In Intelligent Content

After the scaffold creates the directory structure, populate:

**`migrations/<module>/src/lib.rs`**: Replace the template with actual PyO3 function
signatures and struct definitions derived from the Cython/C++ source. Include TODO
comments where implementation logic goes.

**`migrations/<module>/python/<module>.py`**: If the module is stateless/numeric, keep
the fallback wrapper. If it uses async/callbacks/state, replace with the Rust-only
variant.

**`migrations/<module>/analysis.md`**: Fill in all sections:
- API surface with exact type signatures from source
- Key source code snippets (copy relevant sections)
- Data structure mapping (C++ types → Rust equivalents)
- Suggested crate dependencies with rationale
- Existing test cases found in hummingbot
- Fallback feasibility assessment with rationale
- Known complexity areas

**`migrations/<module>/tests/test_<module>.py`**: Replace placeholder with actual
test scaffolds derived from hummingbot's existing tests.

### 5. Return Summary

Return to the primary session:
- What was created (list of files)
- Module API summary
- Key challenges identified
- Suggested implementation approach
- Whether fallback is feasible
- Next command to run: `pixi run test-migration <module>`
```

- [ ] **Step 3: Verify skill is discoverable**

Run: `ls ~/.claude/skills/migrate-module.md && ls ~/.claude/agents/domain/rust-migration-scaffolder.md`
Expected: both files exist

- [ ] **Step 4: Commit**

```
git add ~/.claude/skills/migrate-module.md ~/.claude/agents/domain/rust-migration-scaffolder.md
git commit -m "feat: add /migrate-module skill and rust-migration-scaffolder agent"
```

---

## Task 8: End-to-End Validation

- [ ] **Step 1: Run full test suite**

Run: `pixi run test`
Expected: all tests PASS (existing + new)

- [ ] **Step 2: Run lint and format**

Run: `pixi run quality`
Expected: all PASS

- [ ] **Step 3: Dry-run scaffold against issue #20**

Run: `/migrate-module 20`
Expected: Agent creates `migrations/pubsub/` with all scaffold files, returns summary

- [ ] **Step 4: Verify scaffold output**

Check:
- `migrations/pubsub/Cargo.toml` has valid TOML
- `migrations/pubsub/src/lib.rs` has `register()` function with pubsub-specific signatures
- `migrations/pubsub/analysis.md` has all sections populated with source analysis
- `migrations/pubsub/status.json` shows `"status": "scaffolded"`
- Root `Cargo.toml` has `"migrations/pubsub"` in workspace members

- [ ] **Step 5: Verify list-migrations**

Run: `pixi run list-migrations`
Expected: Shows pubsub migration with scaffolded status

- [ ] **Step 6: Final commit**

> **Note:** Before staging, remove the dry-run scaffold created in Step 3 to avoid committing it:
> `git rm -r --cached migrations/pubsub/ 2>/dev/null; rm -rf migrations/pubsub/`

```
git add scripts/ tests/unit/ pyproject.toml Cargo.toml
git commit -m "feat: rust migration factory - complete tooling implementation"
```
