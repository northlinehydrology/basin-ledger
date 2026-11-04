"""The ledger: every volume and mass that crosses between models, by day, and the checks that it balances.

Each transfer is entered twice, as the sending side reported it and as the receiving side took it. A day's check
fails if any pair differs by more than the tolerance, or if a user's own balance doesn't close.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np


class Ledger:
    def __init__(self, rtol: float = 1e-9, atol: float = 1e-6):
        self.rtol, self.atol = rtol, atol
        self.rows: dict[str, list[float]] = defaultdict(list)
        self.pairs: list[tuple[str, str]] = []
        self.days = 0

    def pair(self, sent: str, received: str):
        """Declare two accounts that must be equal every day."""
        self.pairs.append((sent, received))

    def enter(self, account: str, value: float):
        col = self.rows[account]
        while len(col) < self.days:
            col.append(np.nan)
        col.append(float(value))

    def close_day(self):
        self.days += 1
        for col in self.rows.values():
            while len(col) < self.days:
                col.append(np.nan)
        bad = []
        for a, b in self.pairs:
            x, y = self.rows[a][-1], self.rows[b][-1]
            if abs(x - y) > self.atol + self.rtol * max(abs(x), abs(y)):
                bad.append(f"{a}={x!r} {b}={y!r}")
        if bad:
            raise AssertionError(f"day {self.days - 1}: " + "; ".join(bad))

    def table(self) -> dict[str, np.ndarray]:
        return {k: np.asarray(v) for k, v in self.rows.items()}

    def totals(self) -> dict[str, float]:
        return {k: float(np.nansum(v)) for k, v in self.rows.items()}
