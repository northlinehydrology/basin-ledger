"""Two-way stream-aquifer exchange: MODFLOW 6 river leakage <-> SWAT+ channels, explicit with a one-day lag.

MODFLOW 6's river package (RIV) computes the exchange between each river cell and the aquifer from the river stage
and the head. Each day, after the solve, the exchange is summed per SWAT+ channel through a channel map (which RIV
entries belong to which channel). The next day it goes to SWAT+:

- **swatplus-bmi 0.2.0 and later:** as the channel's groundwater exchange
  (``channel_water__groundwater_volume_exchange_rate``, positive into the channel). A gain joins the channel's inflow
  before routing. A loss comes out of the day's outflow, no more than is there, and counts as SWAT+'s channel
  seepage. Reading the variable after the day gives what was actually exchanged, which is what the ledger enters.
- **Earlier versions:** a net discharge to the stream enters the channel as a SWAT+ point source, ``gw_<channel>``.
  A net leakage from the stream is taken as a SWAT+ water allocation demand, ``seep_<channel>``. A negative point
  source would not do: SWAT+ 62.0.1 records a negative point source in full even when the channel can't supply it.

SWAT+'s own aquifers are set to pass recharge through (``swatplus.aquifer_pass_through``: no return flow, revap or
deep recharge), so groundwater reaches the streams once, through MODFLOW 6. The ledger holds SWAT+'s aquifer outflow
at zero every day.

**Limited by supply** (``[exchange] limit``, on by default): a losing reach can't take more than its channel carries
that day. Before the solve, each coupled channel's loss is predicted at its entries' stages and the day's starting
heads. Where it is more than the channel's flow that day, the channel's stages are lowered by one depth, no entry
below its bottom, until the predicted loss fits (``limit_to_supply``). Lowering the stage is the smooth form of
the river drying: the reach loses less, and gains more where the head is above it. The heads move during the solve,
so a small shortfall can remain; it stays in the ledger. Without the limit, the Clam's headwater channels, left
nearly dry once SWAT+'s aquifers pass recharge through, lost 84 million m3 to MODFLOW 6 that they didn't have.

Other limits of this version:
- MODFLOW 6's river stage is fixed in its input unless the example's ``[rivers]`` section sets it from the surface
  model's channel depth (``stage = "surface_depth"``; SWAT+'s depth needs swatplus-bmi 0.2.0);
- the lag moves water by a day but keeps its volume; the last day's exchange is reported as in transit.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .modflow6 import Modflow6


class ChannelMap:
    """Which entries of a MODFLOW 6 river package belong to which SWAT+ channel."""

    def __init__(self, channels: list[str], entry_channel: np.ndarray):
        self.channels = channels
        self.entry_channel = entry_channel  # per package entry: index into channels, or -1 (not coupled)

    @classmethod
    def from_spec(cls, spec: str, folder: Path, mf6: Modflow6, package: str, swat_channels: list[str]):
        nodes = mf6.package_nodes(package)
        if spec.startswith("all:"):
            ch = spec[4:]
            if ch not in swat_channels:
                raise KeyError(f"exchange map: {ch!r} is not a SWAT+ channel")
            return cls([ch], np.zeros(len(nodes), dtype=int))
        entry = np.full(len(nodes), -1)
        chans: list[str] = []
        with open(folder / spec, newline="") as f:
            for r in csv.DictReader(f):
                ch = r["object"]
                if ch not in swat_channels:
                    raise KeyError(f"{spec}: {ch!r} is not a SWAT+ channel")
                if ch not in chans:
                    chans.append(ch)
                n = int(r["node"]) if r.get("node") else mf6.node(int(r["layer"]), int(r["row"]), int(r["col"]))
                hit = np.flatnonzero(nodes == n)
                if len(hit) == 0:
                    raise ValueError(f"{spec}: cell {n} has no {package} entry")
                entry[hit] = chans.index(ch)
        return cls(chans, entry)


def limit_to_supply(stage: np.ndarray, rbot: np.ndarray, cond: np.ndarray, head: np.ndarray, entry_channel: np.ndarray,
                    available: np.ndarray, iterations: int = 60) -> tuple[np.ndarray, np.ndarray]:
    """Stages lowered so that no channel's predicted loss is more than it has.

    Per entry, MODFLOW 6's river package takes ``cond * (stage - max(head, rbot))`` from the river when that is
    positive. For each channel (``entry_channel``, -1 for entries not coupled) whose total is more than
    ``available`` (m3 for the day), its entries' stages are lowered by one depth d, ``max(stage - d, rbot)``, with d
    found by bisection. At d = max(stage - rbot) the channel takes nothing, so a d always exists. Returns the new
    stages and each channel's d (m, 0 where nothing was lowered)."""
    stage = np.asarray(stage, float).copy()
    floor = np.maximum(head, rbot)

    def loss(st, sel):
        return float(np.sum(cond[sel] * np.clip(st[sel] - floor[sel], 0.0, None)))

    lowered = np.zeros(len(available))
    for i, have in enumerate(np.maximum(available, 0.0)):
        sel = np.flatnonzero(entry_channel == i)
        if len(sel) == 0 or loss(stage, sel) <= have:
            continue
        lo, hi = 0.0, float(np.max(stage[sel] - rbot[sel]))
        s0 = stage.copy()
        for _ in range(iterations):
            mid = 0.5 * (lo + hi)
            s0[sel] = np.maximum(stage[sel] - mid, rbot[sel])
            lo, hi = (lo, mid) if loss(s0, sel) <= have else (mid, hi)
        stage[sel] = np.maximum(stage[sel] - hi, rbot[sel])
        lowered[i] = hi
    return stage, lowered


def requests(due: dict[str, float]) -> dict[str, float]:
    """Yesterday's exchange (m3 per channel, positive to the stream) as today's SWAT+ routes."""
    out = {}
    for ch, v in due.items():
        out[f"swat:point_source:gw_{ch}"] = max(v, 0.0)
        out[f"swat:place_of_use:seep_{ch}"] = max(-v, 0.0)
    return out


class StreamExchange:
    def __init__(self, mf6: Modflow6, package: str, cmap: ChannelMap):
        self.mf6, self.package, self.map = mf6, package, cmap
        P = package.upper()
        self._cond = mf6.get("COND", mf6.model, P).astype(float)
        self._rbot = mf6.get("RBOT", mf6.model, P).astype(float)

    def limit(self, available: dict[str, float]) -> dict[str, float]:
        """Lower today's stages where a channel would lose more than ``available`` (m3 for the day), before the
        solve. Returns the depth each channel was lowered by, m."""
        n = self.mf6.nbound(self.package)
        stage = self.mf6.get("STAGE", self.mf6.model, self.package.upper()).astype(float)
        head = self.mf6.head()[self.mf6.package_nodes(self.package)]
        new, d = limit_to_supply(stage[:n], self._rbot[:n], self._cond[:n], head, self.map.entry_channel[:n],
                                 np.array([available[c] for c in self.map.channels]))
        if np.any(d > 0):
            stage[:n] = new
            self.mf6.set_stage(self.package, stage)
        return dict(zip(self.map.channels, d.tolist()))

    def after_solve(self) -> dict[str, float]:
        """Today's exchange per channel (m3, positive to the stream), due in SWAT+ tomorrow."""
        q = self.mf6.simvals(self.package)  # m3 d-1, positive into the aquifer
        e = self.map.entry_channel
        return {ch: -float(q[e == i].sum()) for i, ch in enumerate(self.map.channels)}
