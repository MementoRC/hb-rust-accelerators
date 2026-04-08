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

    pattern = r'(members\s*=\s*\[)(.*?)(\])'
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
    if project_root is None:
        project_root = PROJECT_ROOT

    ws = project_root / "migrations" / module_name
    if ws.exists():
        raise FileExistsError(f"Migration workspace already exists: {ws}")

    (ws / "src").mkdir(parents=True)
    (ws / "python").mkdir()
    (ws / "tests").mkdir()

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
        f"## Fallback Feasibility\n\nTODO: Agent will assess if pure-Python fallback is practical.\n\n"
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
    issue = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    tier = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    result = scaffold_workspace(name, path, issue, [], tier)
    print(f"Created migration workspace: {result}")
