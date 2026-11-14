"""hummingbot.core.data_type.order_expiration_entry — Rust-accelerated with Python fallback.

Provides OrderExpirationEntry, a lightweight value type used by paper_trade_exchange
to track per-order expiration bookkeeping. Originally implemented as a Cython wrapper
around a C++ struct; replaced here with a pure-Python fallback and an optional
Rust-accelerated variant.

Public API (mirrors original Cython class):
    OrderExpirationEntry(trading_pair, order_id, timestamp, expiration_ts)
    .trading_pair       -> str
    .order_id           -> str
    .timestamp          -> float
    .expiration_timestamp -> float
    .__repr__()         -> str
    .__lt__(other)      -> bool   (sort by expiration_timestamp, then order_id)
    .__le__(other)      -> bool   (same key as __lt__)
    .__gt__(other)      -> bool   (same key as __lt__)
    .__ge__(other)      -> bool   (same key as __lt__)
    .to_pandas(entries) -> pd.DataFrame  (classmethod)
"""

from __future__ import annotations

try:
    # The PyO3 submodule is not registered in sys.modules, so a dotted
    # "from _core.order_expiration_entry import ..." fails; use attribute access.
    from rust_accelerators._core import order_expiration_entry as _oee

    OrderExpirationEntry = _oee.OrderExpirationEntry
    _ACCELERATED = True
except ImportError:
    from rust_accelerators._pure_order_expiration_entry import (  # noqa: F401
        OrderExpirationEntry,
    )

    _ACCELERATED = False


def is_accelerated() -> bool:
    """Return True if Rust acceleration is available for order_expiration_entry."""
    return _ACCELERATED
