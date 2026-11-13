"""Create a migration workspace for a hummingbot module."""

from __future__ import annotations

import keyword
import re
import sys
from datetime import date
from pathlib import Path

from scripts.migration_config import MigrationStatus, write_status

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_MODULE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _validate_module_name(name: str) -> None:
    """Reject names that are not valid Rust crate / Python module identifiers."""
    if not _MODULE_NAME_RE.fullmatch(name) or keyword.iskeyword(name):
        raise ValueError(
            f"Invalid module name {name!r}: must match {_MODULE_NAME_RE.pattern} "
            "(lowercase letter first, then lowercase letters, digits or '_') "
            "and must not be a Python keyword"
        )


def _read_template(name: str) -> str:
    return (TEMPLATES_DIR / name).read_text()


def _update_cargo_workspace(project_root: Path, member_path: str) -> None:
    """Add a member to the [workspace] section in root Cargo.toml."""
    cargo_path = project_root / "Cargo.toml"
    text = cargo_path.read_text()

    pattern = r"(members\s*=\s*\[)(.*?)(\])"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        members_content = match.group(2)
        if member_path not in members_content:
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
    """Create a migration workspace directory with scaffold files."""
    _validate_module_name(module_name)
    if project_root is None:
        project_root = PROJECT_ROOT

    ws = project_root / "migrations" / module_name
    if ws.exists():
        raise FileExistsError(f"Migration workspace already exists: {ws}")

    (ws / "src").mkdir(parents=True)
    (ws / "python").mkdir()
    (ws / "tests").mkdir()

    # Create __init__.py files so the workspace is importable as a package
    # (required for test imports like: from migrations.<name>.python.<name> import ...)
    if not (project_root / "migrations" / "__init__.py").exists():
        (project_root / "migrations" / "__init__.py").write_text(
            "# Migration workspaces package namespace.\n"
        )
    (ws / "__init__.py").write_text(f"# {module_name} migration workspace.\n")
    (ws / "python" / "__init__.py").write_text(f"# Python wrappers for {module_name} migration.\n")
    (ws / "tests" / "__init__.py").write_text(f"# Tests for {module_name} migration.\n")

    class_name = "".join(part.capitalize() for part in module_name.split("_"))

    cargo_tmpl = _read_template("migration_cargo.toml.tmpl")
    (ws / "Cargo.toml").write_text(cargo_tmpl.format(module_name=module_name))

    lib_tmpl = _read_template("migration_lib.rs.tmpl")
    (ws / "src" / "lib.rs").write_text(lib_tmpl.format(module_name=module_name))

    wrapper_tmpl = _read_template("migration_wrapper.py.tmpl")
    (ws / "python" / f"{module_name}.py").write_text(
        wrapper_tmpl.format(module_name=module_name, module_path=module_path)
    )

    test_tmpl = _read_template("migration_test.py.tmpl")
    (ws / "tests" / f"test_{module_name}.py").write_text(
        test_tmpl.format(module_name=module_name, class_name=class_name)
    )

    (ws / "analysis.md").write_text(
        f"Implementation target: Claude Code session in rust-accelerators.\n"
        f"Follow the metrics module pattern in src/lib.rs for PyO3 conventions.\n\n"
        f"# {module_path} Migration Analysis\n\n"
        f"**Issue**: #{issue_number}\n"
        f"**Tier**: {tier}\n"
        f"**Source files**: {', '.join(source_files) or 'none listed'}\n\n"
        f"## Original API Surface\n\nTODO: Agent will populate from source analysis.\n\n"
        f"## Data Structures\n\nTODO: Agent will populate C++ → Rust mapping.\n\n"
        f"## Suggested Crate Dependencies\n\nTODO: Agent will suggest based on source analysis.\n\n"
        f"## Fallback Feasibility\n\n"
        f"TODO: Agent will assess if pure-Python fallback is practical.\n\n"
        f"## Existing Tests\n\nTODO: Agent will extract from hummingbot test suite.\n\n"
        f"## Known Complexity\n\nTODO: Agent will flag tricky patterns.\n"
    )

    status = MigrationStatus(
        issue_number=issue_number,
        module=module_path,
        status="scaffolded",
        created=str(date.today()),
        source_files=source_files,
        tier=tier,
    )
    write_status(ws, status)

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
    try:
        _validate_module_name(name)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    issue = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    tier = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    result = scaffold_workspace(name, path, issue, [], tier)
    print(f"Created migration workspace: {result}")
