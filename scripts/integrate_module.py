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
