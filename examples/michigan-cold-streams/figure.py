"""Map of the screen's gage basins by score, with the tracker's data centers, projects and inquiries.

    uv run --group gis --group examples python examples/michigan-cold-streams/figure.py

Writes ``screen-map.png`` beside this file, from ``screen.csv`` and the cache fetch.py fills.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import shape

from fetch import data_dir

HERE = Path(__file__).parent
LABELS = 5  # how many of the top-scoring basins get a name
ALSO = {"USGS-04118500"}  # the Rogue, also labeled


def _patches(geom):
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    return [MplPolygon(list(p.exterior.coords)) for p in polys]


def main():
    d = data_dir()
    rows = list(csv.DictReader(open(HERE / "screen.csv")))
    fig, ax = plt.subplots(figsize=(7.5, 8.5), dpi=150)
    counties = [shape(f["geometry"]) for f in json.loads((d / "counties.geojson").read_text())["features"]]
    ax.add_collection(PatchCollection([p for c in counties for p in _patches(c)], facecolor="#f4f4f2",
                                      edgecolor="#c9c9c4", linewidth=0.4))
    # largest basins first so nested ones stay visible
    basins = sorted(((shape(json.loads((d / "basins" / f"{r['site']}.geojson").read_text())["features"][0]["geometry"]),
                      float(r["score"]), r) for r in rows), key=lambda b: -b[0].area)
    cmap = plt.get_cmap("viridis")
    lo, hi = min(b[1] for b in basins), max(b[1] for b in basins)
    for geom, score, _ in basins:
        ax.add_collection(PatchCollection(_patches(geom), facecolor=cmap((score - lo) / (hi - lo)), alpha=0.85,
                                          edgecolor="white", linewidth=0.5))
    tracker = json.loads((d / "tracker.json").read_text())
    for kind, marker, label in (("existing", "s", "existing data center"), ("projects", "^", "project or proposal"),
                                ("actions", "o", "inquiry")):
        pts = [(r["lon"], r["lat"]) for r in tracker.get(kind, []) if r.get("lon") is not None]
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], marker=marker, s=18, facecolor="none",
                   edgecolor="#b2182b", linewidth=0.9, label=label, zorder=5)
    for i, r in enumerate(rows):
        if i >= LABELS and r["site"] not in ALSO:
            continue
        ax.annotate(f"{i + 1}. {r['name'].split(' AT ')[0].split(' NEAR ')[0].split(' NR ')[0].title()}",
                    (float(r["lon"]), float(r["lat"])), xytext=(6, -2), textcoords="offset points", fontsize=7.5,
                    zorder=6, bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.8})
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(lo, hi))
    fig.colorbar(sm, ax=ax, shrink=0.45, pad=0.01, label="screen score")
    ax.legend(loc="lower left", fontsize=7.5, frameon=False)
    ax.set_xlim(-90.5, -82.3)
    ax.set_ylim(41.6, 47.6)
    ax.set_aspect(1 / 0.72)  # about 1/cos(44 deg)
    ax.set_axis_off()
    ax.set_title("Gaged basins of 100 to 1,500 km² scored for a first cold-stream study", fontsize=10)
    fig.tight_layout()
    fig.savefig(HERE / "screen-map.png", bbox_inches="tight")


if __name__ == "__main__":
    main()
