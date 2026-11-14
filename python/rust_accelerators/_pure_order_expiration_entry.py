"""Pure Python fallback for OrderExpirationEntry.

Extracted as a standalone module so parity tests can import both the Rust
and Python implementations simultaneously without mock tricks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


class OrderExpirationEntry:
    """Pure-Python fallback for OrderExpirationEntry.

    Semantics match the original Cython/C++ implementation exactly:
    - Ordering via __lt__: primary key = expiration_timestamp, secondary = order_id
    - to_pandas: columns are trading_pair, order_id, timestamp, expiration_timestamp
    """

    __slots__ = ("_trading_pair", "_order_id", "_timestamp", "_expiration_timestamp")

    def __init__(
        self,
        trading_pair: str,
        order_id: str,
        timestamp: float,
        expiration_ts: float,
    ) -> None:
        self._trading_pair: str = trading_pair
        self._order_id: str = order_id
        self._timestamp: float = float(timestamp)
        self._expiration_timestamp: float = float(expiration_ts)

    @property
    def trading_pair(self) -> str:
        return self._trading_pair

    @property
    def order_id(self) -> str:
        return self._order_id

    @property
    def timestamp(self) -> float:
        return self._timestamp

    @property
    def expiration_timestamp(self) -> float:
        return self._expiration_timestamp

    def __repr__(self) -> str:
        return (
            f"OrderExpirationEntry('{self._trading_pair}', '{self._order_id}', "
            f"{self._timestamp}, '{self._expiration_timestamp}')"
        )

    def _key(self) -> tuple[float, str]:
        return (self._expiration_timestamp, self._order_id)

    def __lt__(self, other: object) -> bool:
        """C++ operator< semantics: sort by expiration_timestamp, then order_id."""
        if not isinstance(other, OrderExpirationEntry):
            return NotImplemented
        return self._key() < other._key()

    def __le__(self, other: object) -> bool:
        if not isinstance(other, OrderExpirationEntry):
            return NotImplemented
        return self._key() <= other._key()

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, OrderExpirationEntry):
            return NotImplemented
        return self._key() > other._key()

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, OrderExpirationEntry):
            return NotImplemented
        return self._key() >= other._key()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OrderExpirationEntry):
            return NotImplemented
        return (
            self._expiration_timestamp == other._expiration_timestamp
            and self._order_id == other._order_id
            and self._trading_pair == other._trading_pair
            and self._timestamp == other._timestamp
        )

    def __hash__(self) -> int:
        return hash(
            (self._trading_pair, self._order_id, self._timestamp, self._expiration_timestamp)
        )

    @classmethod
    def to_pandas(cls, order_expiration_entries: list[OrderExpirationEntry]) -> pd.DataFrame:
        """Convert a list of entries to a pandas DataFrame.

        Columns: trading_pair, order_id, timestamp, expiration_timestamp

        Note: the original Cython implementation had a bug referencing
        non-existent fields `.expiration` and `.expiration_time`. This
        implementation uses `.expiration_timestamp` consistently.
        """
        import pandas as pd

        columns = ["trading_pair", "order_id", "timestamp", "expiration_timestamp"]
        data = [
            [
                entry.trading_pair,
                entry.order_id,
                entry.timestamp,
                entry.expiration_timestamp,
            ]
            for entry in order_expiration_entries
        ]
        return pd.DataFrame(data=data, columns=columns)
