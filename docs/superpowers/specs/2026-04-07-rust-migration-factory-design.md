# Rust Migration Factory — Design Spec

**Date**: 2026-04-07
**Status**: Reviewed
**Issue Reference**: https://github.com/MementoRC/hummingbot/issues/20 (example)

## Overview

rust-accelerators serves as a **Rust migration factory** — a workbench where Cython/C++
hummingbot modules flagged for Rust migration are scaffolded, developed, tested, and
integrated before being exported to the hummingbot orchestrator.

An upstream tool (hb-cython-framework analysis layer) creates structured GitHub issues
identifying modules suitable for Rust migration. This design adds tooling to consume
those issues, scaffold migration workspaces, and manage the lifecycle through integration.

## Architecture

Three-phase pipeline, developer-assisted via Claude Code:

| Phase | Tool | Input | Output |
|-------|------|-------|--------|
| **Scaffold** | `/migrate-module <issue#>` skill → agent | GitHub issue + hummingbot source | `migrations/<module>/` workspace |
| **Develop** | Claude Code session (manual) | Scaffold + analysis doc | Working Rust implementation |
| **Integrate** | `pixi run integrate-module <module>` | Completed migration workspace | Module promoted to main package |

### Design Principles

- **Isolation**: Each migration lives in its own workspace under `migrations/`. Multiple migrations can proceed in parallel.
- **Self-contained**: The analysis doc includes all source context needed for implementation. A future Claude Code session needs only the migration workspace, not the hummingbot checkout.
- **Staging**: Modules live in `rust_accelerators.<module>` temporarily until the hummingbot orchestrator integrates them, at which point they are cleaned from rust-accelerators.
- **Deterministic scripts + intelligent agents**: Pixi tasks handle deterministic file operations. Claude Code agents handle analysis and code generation.

## Phase 1: Scaffold

### Invocation

```
/migrate-module 20
```

The skill primes context and dispatches the `rust-migration-scaffolder` agent.

### Agent Workflow

1. **Fetch issue** via GitHub MCP tools — extract module path, source files, C++ dependencies, API surface, tier.
2. **Read hummingbot source** from local checkout — `.pyx`, `.pxd`, `.cpp`, `.h` files listed in the issue.
3. **Read existing hummingbot tests** for the module (if they exist).
4. **Produce the migration workspace** (see Workspace Layout below).
5. **Update root `Cargo.toml`** to add the workspace member.
6. **Return summary** to primary session: what was created, key challenges, suggested approach.

### Script vs Agent Boundary

The **agent** handles all intelligent work: fetching the issue, reading and analyzing source
code, generating Rust signatures, writing the analysis doc, and deciding which crate
dependencies to suggest.

The **`scaffold_migration.py` script** is a thin validation wrapper called by the agent. It:
- Validates the issue number argument
- Creates the directory structure (`migrations/<module>/src/`, `python/`, `tests/`)
- Writes the boilerplate `Cargo.toml` from a template
- Detects naming conflicts (checks if `migrations/<name>/` exists with a different module
  in `status.json`; if so, uses full path segments like `core_pubsub`)
- Updates root `Cargo.toml` workspace members list

The agent then fills in the scaffolded files with intelligent content.

### Workspace Layout

```
migrations/pubsub/
├── Cargo.toml                  # Workspace member with PyO3 + suggested crate deps
├── src/
│   └── lib.rs                  # Scaffolded PyO3 function signatures, struct defs, TODOs
├── python/
│   └── pubsub.py               # Python wrapper (fallback if feasible, Rust-only if not)
├── tests/
│   ├── test_pubsub.py          # Unit test scaffold derived from existing hummingbot tests
│   └── bench_pubsub.py         # Benchmark scaffold (if applicable)
├── analysis.md                 # Implementation guide (see below)
└── status.json                 # Migration status tracking
```

### analysis.md Contents

The first line must be an implementation context header:

```
Implementation target: Claude Code session in rust-accelerators.
Follow the metrics module pattern in src/lib.rs for PyO3 conventions.
```

Followed by:

- Issue reference and module identity
- Original API surface with type signatures
- Key source code snippets (Cython/C++ originals for reference)
- Data structures requiring Rust equivalents (e.g., `unordered_map` → `HashMap`)
- C++ patterns and their Rust equivalents
- Suggested Rust crate dependencies with rationale
- Existing test cases that should be preserved
- Known complexity areas and things to watch out for
- **Fallback feasibility assessment**: whether a pure-Python fallback is practical for this
  module (feasible for numeric/stateless functions; not feasible for async, callbacks,
  shared state). If not feasible, the Python wrapper should import Rust-only with no
  fallback path.

The analysis doc is intentionally self-contained — a Claude Code session should be able
to implement the module by reading only the migration workspace.

### Agent Specification

- **Name**: `rust-migration-scaffolder`
- **Location**: `~/.claude/agents/domain/` (also usable standalone by hummingbot orchestrator)
- **Model**: `sonnet` (analysis work)
- **Tools**: GitHub MCP (fetch issue), Read/Write/Edit (scaffold files), Glob/Grep (find source in hummingbot checkout)

### Python Wrapper Strategy

The scaffold agent assesses whether a pure-Python fallback is feasible:

- **Feasible** (numeric, stateless, array operations): Generate a fallback wrapper following
  the `metrics.py` pattern — try Rust import, fall back to pure Python.
- **Not feasible** (async, callbacks, shared state, complex types): Generate a Rust-only
  wrapper that imports from `_core` with no fallback. The wrapper still provides the public
  Python API and type hints, but raises `ImportError` if the Rust extension is not built.

The agent records this decision in `analysis.md` with rationale.

## Phase 2: Develop

Manual phase — the developer opens a Claude Code session in rust-accelerators and works
within the `migrations/<module>/` workspace to implement the Rust module.

The session uses `analysis.md` as its primary context. The existing `metrics.py` / `lib.rs`
pattern serves as a reference for PyO3 conventions.

### Testing During Development

```
pixi run test-migration pubsub
```

This task builds the **entire crate** (including the migration module temporarily wired into
`src/lib.rs`) via `maturin develop`, then runs the migration's tests. The Cargo workspace
provides code organization and independent `cargo check`/`cargo clippy`, but the loadable
`.so` is always built as part of the main `_core` module because PyO3 `cdylib` modules
must match the expected Python import path (`rust_accelerators._core`).

During development, the migration's Rust code is temporarily referenced from `src/lib.rs`
via a conditional `mod` and submodule registration. The `test-migration` task handles
this wiring automatically and reverts it after testing.

### Status Transitions

- `scaffolded` → `in_progress`: Set automatically when `test-migration` is first run
  (indicates development has started).
- `in_progress` → `tests_passing`: Set automatically when `test-migration` exits with
  code 0 (all tests pass).
- `tests_passing` → `integrated`: Set by the `integrate-module` script after successful
  promotion.

## Phase 3: Integrate

### Invocation

```
pixi run integrate-module pubsub
```

### Integration Script Workflow

1. **Validate** — run the migration's tests to confirm everything passes.
2. **Promote files:**
   - `migrations/pubsub/src/lib.rs` → `src/pubsub.rs`
   - `migrations/pubsub/python/pubsub.py` → `python/rust_accelerators/pubsub.py`
   - `migrations/pubsub/tests/test_pubsub.py` → `tests/unit/test_pubsub.py`
   - `migrations/pubsub/tests/bench_pubsub.py` → `tests/benchmarks/bench_pubsub.py` (if exists)
3. **Wire into main crate:**
   - Add `mod pubsub;` to `src/lib.rs`
   - Register as PyO3 submodule (see Rust Module Structure below)
4. **Update `__init__.py`** — add module-level import (see Python Export Strategy below).
5. **Update root `Cargo.toml`** — merge new dependencies (see Dependency Merge below),
   remove workspace member.
6. **Update `[tool.hummingbot.supersedes]`** — add the migrated module's test paths so
   hummingbot CI knows to skip its own tests for this module.
7. **Run full test suite** — ensure integrated module works alongside existing modules.
8. **Archive** — move `analysis.md` to `docs/migrations/pubsub.md`, remove workspace directory.
9. **Update `status.json`** → `integrated` (in archived location).

### Rust Module Structure

The existing `src/lib.rs` registers functions directly on `_core`. With multiple modules,
we use PyO3 submodules:

```rust
// src/lib.rs
mod pubsub;  // Added at integration

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Existing flat functions (metrics) — unchanged
    m.add_function(wrap_pyfunction!(calculate_max_drawdown, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_sharpe_ratio, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_profit_factor, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_all_metrics, m)?)?;

    // New modules as submodules
    let pubsub_module = PyModule::new(m.py(), "pubsub")?;
    pubsub::register(pubsub_module.as_borrowed())?;
    m.add_submodule(&pubsub_module)?;

    Ok(())
}
```

Each migration's `src/lib.rs` must expose a `pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()>`
function that registers its types and functions. This is documented in the scaffold template.

Python imports after integration:

```python
from rust_accelerators._core import calculate_max_drawdown        # existing (flat)
from rust_accelerators._core.pubsub import PubSub                 # new (submodule)
```

The Python wrapper layer hides this — users import `from rust_accelerators.pubsub import PubSub`.

### Python Export Strategy

New modules are exported at the module level in `__init__.py`:

```python
# python/rust_accelerators/__init__.py
from rust_accelerators.__about__ import __version__

# Metrics (existing — flat re-export for backwards compatibility)
from rust_accelerators.metrics import (
    calculate_all_metrics,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    is_accelerated,
)

# Migrated modules (module-level import)
from rust_accelerators import pubsub  # noqa: F401
```

Consumers use `from rust_accelerators.pubsub import PubSub` or
`import rust_accelerators.pubsub as pubsub`. The existing metrics functions remain
as flat re-exports for backwards compatibility.

### Dependency Merge Strategy

The integration script merges `[dependencies]` from the migration's `Cargo.toml` into
the root `Cargo.toml`. Constraints:

- **All migration dependencies must use compatible semver ranges.** If two migrations
  depend on the same crate at incompatible versions, the integration script fails with
  a clear error and the developer resolves manually.
- **Feature flags are merged** (union of features for the same crate).
- The script logs every dependency added or version range widened.

This keeps the script deterministic while handling the common case. Conflicts (rare) are
surfaced for human resolution rather than silently resolved.

## Pixi Tasks

| Task | Command | Purpose |
|------|---------|---------|
| `scaffold-migration` | `python scripts/scaffold_migration.py <issue#>` | Create migration workspace (called by agent or directly) |
| `integrate-module` | `python scripts/integrate_module.py <module>` | Promote completed migration to main package |
| `list-migrations` | `python scripts/list_migrations.py` | Show status dashboard of all migrations |
| `test-migration` | Script: wire module into crate, `maturin develop`, `pytest migrations/<module>/tests/`, unwire | Test a specific migration workspace |

## Configuration

### pyproject.toml

```toml
[tool.hummingbot.migration]
source_checkout = "../../../"
issue_repo = "MementoRC/hummingbot"
```

Default `source_checkout` assumes standard mono-repo layout (`sub-packages/rust-accelerators`
inside hummingbot). Overridable via `HUMMINGBOT_SOURCE_PATH` environment variable.

**Precedence**: `HUMMINGBOT_SOURCE_PATH` env var > `source_checkout` in pyproject.toml.

**Failure behavior**: If the resolved path does not exist or does not contain a
`hummingbot/` directory, the scaffold agent fails early with a clear error message.
The integration script does not need the source checkout.

### Migration Status Tracking

Each migration workspace contains `status.json`:

```json
{
  "issue_number": 20,
  "module": "hummingbot.core.pubsub",
  "status": "scaffolded",
  "created": "2026-04-07",
  "source_files": ["hummingbot/core/pubsub.pyx", "hummingbot/core/pubsub.pxd"],
  "tier": 3
}
```

Status values: `scaffolded` → `in_progress` → `tests_passing` → `integrated`

Transitions are automatic (see Status Transitions in Phase 2).

### Naming Conventions

- Directory: `migrations/<last_segment>/` (e.g., `migrations/pubsub/`)
- Rust module: same as directory name
- Python wrapper: `rust_accelerators.<module>`
- Conflict detection: scaffold script checks if `migrations/<name>/` exists with a
  different `module` value in `status.json`. If conflict detected, uses full path
  segments (e.g., `migrations/core_pubsub/`).

## Cargo Workspace

Each migration is a Cargo workspace member for code organization:

```toml
# Root Cargo.toml
[workspace]
members = [".", "migrations/pubsub", "migrations/order_tracker"]
```

Workspace members support independent `cargo check` and `cargo clippy` during development.
The loadable `.so` is always built as part of the main crate via `maturin develop` because
PyO3 `cdylib` modules must match the expected Python import path.

At integration time, the member is removed and its code merged into the main crate.

## Relationship to Other Components

- **hb-cython-framework** (`../cython-framework`): Handles pure-Python/augmented-Python migration path. Creates the GitHub issues that feed into this process.
- **hummingbot orchestrator**: Consumes finished modules from `rust_accelerators.<module>` and integrates them into hummingbot proper. After integration, modules are cleaned from rust-accelerators.
- **Existing metrics module**: Stays as-is. Was hand-built before this process. New migrations follow the new workflow.
- **`[tool.hummingbot.supersedes]`**: Updated during integration to include the migrated module's test paths, enabling hummingbot CI to skip its own tests for modules that have Rust replacements.
