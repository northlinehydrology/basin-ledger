# Testing Basin Ledger (written Nov 6, 2026, before the tests it plans)

Basin Ledger is only useful if its couplings move water, heat and mass between models without making or losing any,
and without the models fighting. Andrew: "It is extremely important that basinledger WORKS." This note says how the
tests show that, what they cover now, and what is still missing. The Clam (clam-basin-study) found the gaps: its
first coupled run passed every ledger pair and still made or lost water at four links (design.md, "Conservation
across links").

## What a test has to show

1. **Nothing is made or lost at a link.** Every crossing of a model boundary is booked as sent and received, and the
   two agree. Water from outside (a supply, a fixed head, recharge where no surface model runs) is its own account.
2. **Each model's own budget closes**, and the ledger agrees with it.
3. **The coupled answer is right where an independent answer exists**: an analytic solution, a closed energy or mass
   balance, a model run alone.
4. **The models run as their developers ship them**, with only the settings coupling needs, checked at start-up.
5. **Every function works on a real basin**, not only on the synthetic one, with the effects going the way physics
   says they must.
6. **A result doesn't change unless something meant to change it did.**

## Tiers

| Tier | What | Where | When |
|---|---|---|---|
| 0. Units | pure functions: maps, the ledger, the supply limit, the heat balance, the chain, rules, statistics | `tests/`, no models | every push (CI) |
| 1. The run is a test | invariants the ledger checks every day of every run, which stop the run when broken (below) | the driver | every run, any example |
| 2. Synthetic integration | each function on the synthetic example (Osu_1hru and small MODFLOW 6 models), end to end | `tests/`, marked `slow` | every push (CI) and nightly |
| 3. Independent answers | the coupled result against an analytic solution or another closed budget | `tests/` | CI |
| 4. Faithfulness and settings | each model unchanged but for the coupling's settings; wrong settings refused | `tests/` (and swatplus-bmi's own suite) | CI |
| 5. Real basins | every function on a real coupled model: a scenario matrix from a shared warm-up, each run closing, the effects in the right direction, the numbers recorded | the study repo (`clam-basin-study/functional.py`), not here | on demand, after a change to the engine |
| 6. Regression | tier 5's recorded summary compared with the last accepted one, with tolerances | the study repo | on demand |

Tier 5 lives in the study, not in Basin Ledger, because the models are the study's (Basin Ledger is a tool, not a
study). Its results are screening runs: the Clam's calibration stopped short of its targets, so it tests the engine,
not the basin.

## Tier 1: what every run checks

- every ledger pair (sent = received), each day, to its tolerance: recharge; routes (requested = delivered +
  shortfall); the exchange (due = applied + shortfall); each user's balance (withdrawal + gain = consumption +
  return + storage change); the utility chain;
- accounts that must stay zero: SWAT+'s aquifer outflow in two-way mode;
- MODFLOW 6's closure against the day's gross flow, to 1e-6 (`groundwater:closure_share`);
- recharge mapped on each aquifer's own area (`area_rtol`, 1e-6 unless an example turns it off and says why), and
  what the map added or couldn't place booked as `recharge:by_the_map`;
- start-up: SWAT+ on a daily step; in two-way mode its aquifers passing recharge through, nothing in
  `calibration.cal` turning them back on, no channel transmission loss; MODFLOW 6's recharge package one entry per
  cell, no multiplier.

## Coverage now, and the gaps

| Function | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| recharge, one-way | yes | yes | yes | MODFLOW 6 budget | pass-through storage | Clam |
| two-way exchange, supply limit, drains | yes | yes | yes | MODFLOW 6 budget | settings | Clam |
| boundary flows, storage, closure | | yes | yes | | | Clam |
| wells and capture of pumping | | yes | yes (G1, two-way and one-way) | Glover and Balmer (G2) | | Clam |
| water users (CoolingWaterBmi) on SWAT+'s weather | yes | yes | yes (G7) | user balance | | Clam |
| return water to a stream, and its loads | yes (G6) | yes | yes (G6, G7) | | | Clam |
| rules | yes | | yes (one-way) | | | Clam |
| utility chain | yes | yes | yes | | | |
| restarts | | | yes (bit for bit) | | | |
| scenarios from a shared warm-up | | | yes (G5) | | | Clam |
| stream temperature | yes (energy closes) | | yes (G4) | energy | | Clam |
| whole-basin balance | | | yes (G3) | | | Clam |
| NextGen replay | yes | yes | yes | | | Plaster Creek |

Built Nov 6, 2026 (G1 to G7; G7, water users on SWAT+'s weather, was found while building G6). What they turned up:
- SWAT+ 62.0.1 reads `print.prt`'s object rows by position unless `use_obj_labels` is on, and Osu_1hru's rows are out
  of the reader's order: Basin Ledger now switches labels on when it edits the print settings.
- Osu_1hru irrigates and has a point source into its channel, both water from outside, now in the balance.
- `ch_temp`'s single explicit heat-exchange step overshoots the equilibrium temperature on a long reach (Osu_1hru's
  channel reached 90 C); the heat balance integrates it exactly.
- MODFLOW 6 through the coupling's wrapper matches Glover and Balmer within 0.5% of the pumping from day 10.

The gaps, each to be built with its test:

- **G1. Capture of pumping.** In two-way mode the pumping must equal what it takes from storage, from the streams
  (less discharge and more leakage) and across the boundary: `analysis.capture` from a pair of runs, with and without
  the user, and a test that the parts add up.
- **G2. Depletion against Glover and Balmer (1954).** A synthetic aquifer built to match the analytic case (uniform,
  one straight stream with little streambed resistance, far boundaries); MODFLOW 6's depletion through Basin Ledger
  within a stated tolerance of `analytic.glover_depletion`.
- **G3. The whole basin closes.** `balance.basin_balance` (from the Clam's study code) in Basin Ledger: SWAT+'s land,
  lake and channel budgets, the links and MODFLOW 6's budget; tested on the synthetic two-way run.
- **G4. Stream temperature on a run.** The reach heat balance on a synthetic run's outputs (energy closing over the
  run) and, on the Clam, the change with and without a well.
- **G5. Scenarios from a shared warm-up.** One warm-up saved, cases run from it; a test that a case with no change
  matches the unbroken baseline, and that cases differ only after the warm-up.
- **G6. What the return water carries.** A user's constituents and heat reach the receiving reach's ledger as
  masses, and `analysis.concentration_change` gives the percent change at low flow; tested on the synthetic surface
  example.
- **Outfalls:** an `outfall:` route is booked in the ledger only and never reaches SWAT+. A return meant for a stream
  goes through `swat:point_source`. Documented in the routes; a real example that uses `outfall:` for a stream return
  is wrong.

## Tier 5 on the Clam

`clam-basin-study/functional.py` runs, from one warm-up (Oct 2001 to Sep 2002) at stage 3's parameters:

| Case | What it adds |
|---|---|
| base | nothing |
| well | the step 2 well (920 gal/min, all of it leaving the basin) |
| campus | a data center on that well (CoolingWaterBmi), its blowdown back to the well's reach |
| rules | the campus, curtailed when the cold-transitional reach's flow is low, with a drawdown limit at the well |

Each run must close (tier 1); and across the runs:
- the well's pumping equals its capture (G1) within 1%;
- depletion is zero upstream of the well's catchment's outflow and positive at it and below, in the dry months;
- the campus consumes what it evaporates, and its return raises dissolved solids at the receiving reach;
- the rules act on the days they should, and take less water than the campus without them;
- summer stream temperature at the trout reaches with the well is no lower than without it (less groundwater);
- the whole basin closes (G3) in every case.

The summary (`functional.json`) is recorded, and later runs are compared with it (tier 6).
