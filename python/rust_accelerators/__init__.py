"""Rust-accelerated performance modules for hummingbot sub-packages."""

from rust_accelerators.__about__ import __version__
from rust_accelerators.metrics import (
    calculate_all_metrics,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    is_accelerated,
)

__all__ = [
    "__version__",
    "calculate_all_metrics",
    "calculate_max_drawdown",
    "calculate_profit_factor",
    "calculate_sharpe_ratio",
    "is_accelerated",
]
