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
        try:
            build_result = subprocess.run(
                ["pixi", "run", "rust-build-debug"],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as e:
            print(f"Build failed: {e}")
            update_status_for_run(migration_dir, test_passed=False)
            return 1
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
