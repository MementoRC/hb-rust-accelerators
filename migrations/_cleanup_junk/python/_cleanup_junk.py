"""dummy — Rust-accelerated with Python fallback."""

from __future__ import annotations

try:
    from rust_accelerators._core._cleanup_junk import *  # noqa: F401,F403

    _ACCELERATED = True
except ImportError:
    _ACCELERATED = False
    # TODO: Add pure-Python fallback implementations here


def is_accelerated() -> bool:
    """Return True if Rust acceleration is available for _cleanup_junk."""
    return _ACCELERATED
