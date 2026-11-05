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
