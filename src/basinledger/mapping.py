"""Maps between SWAT+ objects and MODFLOW 6 cells, as areas of overlap.

A map is a list of rows (object, cell, area in m2): the part of a cell's area that a SWAT+ object (an aquifer, an HRU,
a catchment) covers. Depth rates move through it by area, so volume is kept exactly: an object's rate times its
mapped area is what the cells receive. Maps come from an example's config, never from code:

    cells = "all"             every cell of the top layer, its whole area, to one object
    cells = "map.csv"         a table: object, layer, row, col, area_m2 (or object, node, area_m2)

A map from GIS (NextGen catchments or SWAT+ HRU polygons intersected with the grid, e.g. with flopy's GridIntersect)
is written to the same table, so the coupling code never sees geometry.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class AreaMap:
    objects: list[str]   # object names, in the order of the source model's grid
    obj: np.ndarray      # row -> index into objects
    node: np.ndarray     # row -> MODFLOW 6 node, 0-based, reduced numbering
    area: np.ndarray     # row -> m2 of overlap

    def mapped_area(self) -> np.ndarray:
        """m2 per object."""
        return np.bincount(self.obj, weights=self.area, minlength=len(self.objects))

    def to_cells(self, rate: np.ndarray, cell_area: np.ndarray) -> np.ndarray:
        """Depth rates per object -> depth rates per cell (same units), conserving volume."""
        vol = np.bincount(self.node, weights=rate[self.obj] * self.area, minlength=len(cell_area))
        return vol / cell_area

    def volume(self, rate: np.ndarray) -> float:
        """Depth rate per object times its mapped area, summed: what leaves the source model."""
        return float(np.sum(rate * self.mapped_area()))

    def check(self, cell_area: np.ndarray, source_area: np.ndarray | None = None, rtol: float | None = None):
        """Cells may not be over-covered; with ``rtol``, each object's mapped area must equal its area in the
        source model (``source_area``, m2) within that tolerance."""
        covered = np.bincount(self.node, weights=self.area, minlength=len(cell_area))
        if np.any(covered > cell_area * (1 + 1e-9)):
            bad = int(np.argmax(covered / cell_area))
            raise ValueError(f"cell {bad} is mapped {covered[bad]:.1f} m2 of {cell_area[bad]:.1f} m2")
        if rtol is not None and source_area is not None:
            m = self.mapped_area()
            off = np.abs(m - source_area) > rtol * source_area
            if off.any():
                i = int(np.argmax(off))
                raise ValueError(f"{self.objects[i]}: mapped area {m[i]:.0f} m2, source model {source_area[i]:.0f} m2")

    @classmethod
    def all_cells(cls, objects: list[str], name: str, nodes: np.ndarray, cell_area: np.ndarray) -> "AreaMap":
        nodes = np.asarray(nodes)
        return cls(list(objects), np.full(len(nodes), objects.index(name)), nodes, cell_area[nodes].astype(float))

    @classmethod
    def from_csv(cls, path: str | Path, objects: list[str], node_of) -> "AreaMap":
        """``node_of(layer, row, col)`` -> 0-based reduced node; rows may give ``node`` instead."""
        obj, node, area = [], [], []
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                if r["object"] not in objects:
                    raise KeyError(f"{path}: {r['object']!r} is not an object of the source model")
                obj.append(objects.index(r["object"]))
                if r.get("node"):
                    node.append(int(r["node"]))
                else:
                    node.append(node_of(int(r["layer"]), int(r["row"]), int(r["col"])))
                area.append(float(r["area_m2"]))
        return cls(list(objects), np.array(obj), np.array(node), np.array(area))
