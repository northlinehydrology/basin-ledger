"""The NextGen hydrofabric as Basin Ledger's spatial frame. Not built yet.

Planned (docs/design.md, NextGen geography):

- **SWAT+ projects from the hydrofabric.** One subbasin, routing unit and aquifer per catchment (``cat-``), one
  channel per flowpath (``wb-``), connected as the hydrofabric's flowpath-nexus network connects them; HRUs split
  within each catchment by land cover, soils and slope. Writes SWAT+'s connection and object files and a lookup
  table (``swat_ids.csv``) of SWAT+ object name against hydrofabric id.
- **Maps to the MODFLOW 6 grid.** Catchments, aquifers and HRUs to cells by area of overlap
  (``maps/catchment_cells.csv``), flowpaths to stream cells by length (``maps/flowpath_cells.csv``), made with flopy's
  GridIntersect and checked against the hydrofabric's areas and lengths.
- **Results keyed to ids.** Nexus flow (the outflow of the channels draining to each nexus), base flow and depletion
  per flowpath, recharge and drawdown per catchment, all under hydrofabric ids, so they compare with the National
  Water Model.

The coupling code never sees geometry: everything here ends as a CSV map or a lookup table named in an example's
config.
"""


def build_swatplus_project(*args, **kwargs):
    raise NotImplementedError("the hydrofabric SWAT+ builder is planned; see docs/design.md, NextGen geography")


def build_maps(*args, **kwargs):
    raise NotImplementedError("hydrofabric-to-grid maps are planned; see docs/design.md, NextGen geography")
