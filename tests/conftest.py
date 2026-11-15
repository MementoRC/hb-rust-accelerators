"""Root test configuration.

``RUST_ACCELERATORS_FORCE_FALLBACK=1`` makes the compiled ``rust_accelerators._core`` extension
unimportable so the pure-Python fallback branches are exercised even when the extension is built.
This must run before anything imports ``rust_accelerators``.
"""

from __future__ import annotations

import os
import sys

import pytest

if os.environ.get("RUST_ACCELERATORS_FORCE_FALLBACK") == "1":
    if os.environ.get("RUST_ACCELERATORS_REQUIRE_RUST") == "1":
        raise pytest.UsageError(
            "RUST_ACCELERATORS_FORCE_FALLBACK=1 and RUST_ACCELERATORS_REQUIRE_RUST=1 are "
            "contradictory; set only one."
        )
    # A None entry makes ``from rust_accelerators._core import ...`` raise ImportError.
    sys.modules["rust_accelerators._core"] = None  # type: ignore[assignment]
