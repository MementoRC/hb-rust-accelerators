"""Rust-accelerated performance modules for hummingbot sub-packages."""

from rust_accelerators.__about__ import __version__
from rust_accelerators.metrics import (
    calculate_all_metrics,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe_ratio,
)
from rust_accelerators.metrics import is_accelerated as _metrics_is_accelerated

__all__ = [
    "__version__",
    "calculate_all_metrics",
    "calculate_max_drawdown",
    "calculate_profit_factor",
    "calculate_sharpe_ratio",
    "is_accelerated",
]

from rust_accelerators import order_expiration_entry  # noqa: E402


def is_accelerated() -> bool:
    """Return True only if every accelerated module is using the Rust backend."""
    return _metrics_is_accelerated() and order_expiration_entry.is_accelerated()
