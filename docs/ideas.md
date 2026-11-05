# Ideas (not decided)

Notes from Andrew Sommerlot, November 4, 2026, recorded so they aren't lost. These are ideas, not decisions, and may
not be done this way. Nothing here is built. The design that is agreed is in `design.md`.

## 1. The aim

Real scenario modeling of what happens to natural systems when industry is added or changed. That means putting all
the users together: agriculture and industry, existing and new. The question is what happens in a long drought, in a
very wet few years, or in a normal stretch, and whether particular points or reaches become problematic. Aggregated
nationally, industry's water use looks small. The interest is cumulative and local.

## 2. Weather regimes and timing

- **Stresses coincide.** Cooling, irrigation and lawn watering all peak in the hot, dry weeks, when flows are lowest
  and warmest. Every user runs on the same weather as the basin model.
- **Drought shows depletion and concentration:**
  - the share of low flow taken;
  - wells depleting streams;
  - undiluted salts and heat;
  - trout-stream temperature thresholds.
- **Wet years show loading:** nutrients, sediment, sewer overflows and high groundwater. Phosphorus against a TMDL is
  mostly a wet-year problem.
- **Normal years show how close a system already is to a limit.**
- **Weather to use:** real past years first (a drought year, a wet stretch, a typical decade), future climate later.
  Ensembles give an honest answer to "how often".

## 3. The baseline includes existing users

The baseline holds:

- reported withdrawals (EGLE in Michigan, USGS elsewhere);
- permitted discharges, with ECHO monitoring reports;
- current land use and wells.

New users go on top. Otherwise an already stressed reach looks fine.

## 4. Per-reach hotspot metrics

On hydrofabric flowpaths, for each weather regime:

- the share of low flow withdrawn and consumed;
- the dilution of returns;
- concentrations against criteria (chloride, phosphorus, temperature);
- drawdown and stream depletion near wells.

Reaches are ranked by how often they exceed a threshold. The output is a map of which reaches are stressed, under
which conditions and with which users. For example, a reach might fail only if both the fab and the irrigation
expansion go in.

## 5. Basins

- **Plaster Creek first,** with one gage.
- **Then the Lower Grand, for hotspots.** It has several gages, mixed agriculture and industry, and Gaines and Lowell
  inside it.

## 6. A generic ("ghost") water user

For cases where modeling a user's process would take irresponsible assumptions.

- **Defined only by what's known:**
  - withdrawal: a rate, a permitted volume, a seasonal pattern or a reported series;
  - source;
  - consumption, as a fraction range;
  - where and when water returns;
  - quality, as concentrations, loads, or permit limits taken as the upper bound.

  An unknown constituent is left blank, not guessed.
- **The same outputs as other users.** Each is labeled with its provenance: declared, permit, reported or range.
- **Uses:**
  - existing users in the baseline, from reported data with no modeling;
  - proposals with almost no detail ("up to 2 MGD");
  - "how much can this reach take": scale it up at a point until a threshold breaks.
- **Evidence levels for every user.** A user moves up a level only when the evidence supports it.
  1. Generic: declared or reported values.
  2. Ratio-based: effluent guidelines or published ratios.
  3. Process model: weather-driven physics, like the cooling model.
- **Where it might live:** the synthetic test user (`basinledger.testing.SyntheticUser`) is close to it already. One
  possible home is `waterledger-models`, so Water Ledger's calculator and Basin Ledger share it. Not decided.

## 7. Kinds of users under discussion

This is context, not a list to build:

- data centers;
- gas power plants;
- semiconductor fabs;
- battery plants and battery materials;
- hydrogen;
- food and meat processing;
- large livestock operations;
- irrigation wells;
- bottled water;
- oil and gas produced water (Texas).

Andrew is lukewarm on mines, and finds bottled water interesting.

**Measures shared by all of them:**

- withdrawal and consumption, average and peak;
- drawdown and stream depletion;
- low-flow context;
- nitrogen and phosphorus;
- sediment;
- salts and chloride;
- temperature.

PFAS is context only.

## 8. Utility water: where it comes from, and how to model it (decided direction, November 4, 2026)

Andrew approved this direction. The facts come from public sources collected in Northline's site record for Gaines
Township.

**The facts:**
- The Byron-Gaines Utility Authority (BGUA) buys water wholesale from the City of Wyoming through one connection. A
  second connection is estimated at over $20 million.
- Wyoming's plant treats Lake Michigan water. Its capacity is 120 MGD (Prein & Newhof) or 90 MGD (the city's page)
  [A: a range]. Average use is about 40 MGD.
- Wyoming's 2023 reliability study, as Georgetown Township summarized it, finds the system "rapidly heading toward
  unsustainable capacity levels", with expansion projected for 2034.
- BGUA has 3 tanks with 4 MG of storage combined, and a 2 MG tank planned.
- Sewered wastewater goes to Wyoming's Clean Water Plant (24 MGD, NPDES MI0024392), which discharges to the Grand River.

**How to model it:**

1. **The utility chain, for capacity.** For a campus on utility water, the binding question is infrastructure:
   - the plant's capacity, and its headroom on the peak day;
   - the single connection;
   - storage.

   Basin Ledger's utility chain takes these facts as cited inputs, with the plant's capacity as a range [A]. The
   Plaster Creek demo shows this as the utility case's result, since the creek sees almost nothing in that case.
2. **Where the water ends up.** The campus gets lake water. What it consumes evaporates. The rest returns to the
   Grand River below Wyoming's Clean Water Plant, with its salts and phosphorus; the plant passes salts through. That
   is outside Plaster Creek's domain and is stated as such there. In the Lower Grand, the return is a point source on
   the Grand.
3. **No hydrologic model of Lake Michigan.** The withdrawal makes no measurable difference to the lake. Consumptive use
   is reported as Great Lakes Compact accounting only.
4. **Utility well fields are pumping users.** Many Michigan utilities pump their own wells inside the basin. A utility's
   wells are treated as a generic user, with reported withdrawals (EGLE, SDWIS sources) at its well locations. A campus
   on such a utility then shows up in the groundwater through the utility's added pumping on its peak days.

## 9. HEC-RAS (1D and 2D) and HEC-HMS as BMI components (not decided, November 5, 2026)

Andrew's view: building BMI wrappers for them is worth it in itself, as a demonstration of the work. No maintained
BMI exists for either.

1. **Why.**
   - These are the models engineering firms, FEMA studies and municipal stormwater reviews use.
   - Basin Ledger's scenarios driving an existing HMS or RAS model matters for subconsultant work and for
     credibility with reviewers.
   - Both are public domain (USACE).
2. **RAS 2D is the most interesting.**
   - **Floods and wet years:** overbank flow, floodplain storage, streets and parking. This is the wet-years regime
     in section 2.
   - **Rain on the mesh** (RAS 6, with curve-number or Green-Ampt infiltration), so a campus's new pavement and
     detention show up as local flooding.
   - **Plaster Creek** has a flooding history in Kentwood and Grand Rapids. A 2D flood scenario with and without the
     campus could be checked against high-water marks and the gage's stage record.
   - **RAS 1D** gives depth, velocity and wetted area at low flow (habitat and intakes). It also gives a better
     stream stage for MODFLOW 6 than t-route's depth, and 1D water temperature for warm returns. RAS water quality is
     1D only.
3. **The wrapper pattern: saved-state stepping,** the same idea as swatplus-bmi's snapshots.
   - **RAS:** unsteady plans write restart files and hot-start from them. `update()` runs one interval from the last
     restart. `get_value` and `set_value` read and write the HDF5 results and the boundary conditions: inflows from
     Basin Ledger, stage to MODFLOW 6.
   - **HMS:** save and start states on simulation runs, driven through its Jython scripting.
   - **Cost:** there is a restart overhead each step. That's fine for daily steps through events and wet seasons, and
     slow for 30 years of 2D. 2D would run on events and wet periods, with SWAT+, NextGen or 1D covering the long runs.
   - **Python tools:** rashdf and ras-commander for HDF5 and plan handling. RAS 6 has Linux solvers.
4. **Questions to check before building:**
   - **Meshes:** building a 2D mesh and geometry probably needs RAS Mapper (Windows). That would be a one-time Windows
     step, with the wrapper and the runs on Linux.
   - **Restarts:** what the restart files carry, and whether a hot start reproduces an unbroken run bit for bit (the
     same test as swatplus-bmi's).
   - **HMS:** whether state saving works through Jython on Linux.
   - **Inputs:** 3DEP 1 m lidar for Michigan, roughness from NLCD, and calibration to high-water marks and gage stage.
5. **A possible order:**
   1. swatplus-bmi 0.2.0;
   2. the Plaster Creek groundwater calibration;
   3. a hecras-bmi wrapper on one reach in 1D, proving restart stepping;
   4. RAS 2D on Plaster Creek's flood-prone reach;
   5. HMS, mainly as an event comparison against Calvin University's existing Plaster Creek HMS model (to confirm).

   Each wrapper would likely be its own repository, like swatplus-bmi, with Basin Ledger using it.
