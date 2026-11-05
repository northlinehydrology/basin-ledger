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

Limits of this first version:
- MODFLOW 6's river stage is fixed in its input unless the example's ``[rivers]`` section sets it from the surface
  model's channel depth (``stage = "surface_depth"``; SWAT+'s depth needs swatplus-bmi 0.2.0);
- the lag moves water by a day but keeps its volume; the last day's exchange is reported as in transit;
- a losing reach SWAT+ can't supply is entered as a shortfall: water MODFLOW 6 took from a stream that, in SWAT+,
  wasn't there. The next step is to lower the reach's stage for the next day when that happens.
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

    def after_solve(self) -> dict[str, float]:
        """Today's exchange per channel (m3, positive to the stream), due in SWAT+ tomorrow."""
        q = self.mf6.simvals(self.package)  # m3 d-1, positive into the aquifer
        e = self.map.entry_channel
        return {ch: -float(q[e == i].sum()) for i, ch in enumerate(self.map.channels)}
