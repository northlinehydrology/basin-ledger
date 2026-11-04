"""SWAT+ recharge into MODFLOW 6, one day at a time (one-way).

SWAT+ reports each aquifer's recharge as a depth rate (``soil_water_table__recharge_rate``, m s-1, read through
swatplus-bmi after the day). The area map spreads it over MODFLOW 6 cells by area of overlap, and the cells' rates go
into the recharge package for the same day. ``sent`` is the volume leaving SWAT+ (rate x mapped area); after the solve,
``received`` is what MODFLOW 6's recharge package took in. The ledger holds them equal.
"""

from __future__ import annotations

import numpy as np

from ..mapping import AreaMap
from ..units import DAY
from .modflow6 import Modflow6

RECHARGE = "soil_water_table__recharge_rate"


class RechargeLink:
    def __init__(self, swat, mf6: Modflow6, amap: AreaMap, package: str = "rch"):
        self.swat, self.mf6, self.map, self.package = swat, mf6, amap, package
        self._buf = np.empty(swat.get_grid_size(swat.get_var_grid(RECHARGE)), dtype=np.float32)
        names = swat.get_grid_object_names(swat.get_var_grid(RECHARGE))
        if list(names) != amap.objects:
            raise ValueError(f"area map objects {amap.objects} differ from SWAT+'s aquifers {list(names)}")
        if swat.get_var_units(RECHARGE) != "m s-1":
            raise ValueError(f"unexpected recharge units {swat.get_var_units(RECHARGE)}")

    def transfer(self) -> float:
        """Read the day's recharge from SWAT+ (after its update) and set it in MODFLOW 6 (after prepare_day).
        Returns the volume sent, m3."""
        self.swat.get_value(RECHARGE, self._buf)
        rate = self._buf.astype(np.float64) * DAY  # m d-1 per aquifer
        unmapped = np.setdiff1d(np.unique(self.map.node), self.mf6.package_nodes(self.package))
        if len(unmapped):
            raise ValueError(f"{len(unmapped)} mapped cells have no entry in MODFLOW 6's {self.package} package")
        self.mf6.set_recharge(self.package, self.map.to_cells(rate, self.mf6.cell_area))
        return self.map.volume(rate)  # one day

    def received(self) -> float:
        """Volume the recharge package took in on the day just solved, m3."""
        return float(self.mf6.simvals(self.package).sum())
