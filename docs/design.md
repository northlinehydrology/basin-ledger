# Basin Ledger: design

Basin Ledger is the study engine behind Northline's water studies. It couples watershed, groundwater and water-user
models through BMI and steps them together one day at a time. It is a sibling of
[Water Ledger](https://waterledger.org). Water Ledger accounts for one campus's water: what it withdraws, consumes and
returns, from public data, as a calculator. Basin Ledger accounts for a whole basin's water. It balances quantity and
quality day by day across the coupled models, so a study can say where a large user's water comes from, where it goes,
and what changes in the streams and the aquifer.

Status (Nov 4, 2026): the water-user interface, the SWAT+ to MODFLOW 6 one-way coupling and the ledger work and are
tested on a synthetic example. The rest of this note is design. Sections say which parts are built.

## Principles

1. **A general engine, with places as examples.** Nothing in `basinledger` is tied to a place. A location is an
   example: one config file that wires real models for one basin and its water users, a script that fetches its public
   data, and a short write-up. An example is also a study's starting point. A public example shows the engine working.
   A client study is a private example built the same way, kept outside this repository. The engine's own tests run on
   a small synthetic example.
2. **Water users are pluggable.** A water user is a BMI component behind one common interface. Data center cooling
   (`CoolingWaterBmi`, from `waterledger-models`) is the first. Mines, battery and EV plants, chip fabs, food processing
   and hydrogen will follow in `waterledger-models`. Each one plugs into the same driver, utility chain and couplings
   with no engine changes. No user type is special-cased.
3. **Every transfer balances, and tests hold it to that.** Each volume or mass that crosses between models is entered
   in the ledger twice, as sent and as received. A day where the two differ stops the run. Each model's own budget
   must close too.
4. **Models stay whole.** Each model runs as its developers ship it. SWAT+ runs through
   [swatplus-bmi](https://github.com/northlinehydrology/swatplus-bmi)
   ([doi:10.5281/zenodo.23963201](https://doi.org/10.5281/zenodo.23963201)), whose output is byte-for-byte identical
   to stock SWAT+. MODFLOW 6 runs through USGS's own shared library. Couplings set fluxes between days; they don't edit
   model code.
5. **Packages first.** Water-user physics lives in `waterledger-models`, SWAT+ access in `swatplus-bmi`. Basin Ledger
   holds only the coupling, the accounting and the rules. Changes those packages need are written as requests
   (`docs/requests.md`).

## Layout

```
src/basinledger/
  config.py            an example's TOML config: models, maps, wells, users, routes
  driver.py            Basin: steps every model one day at a time and keeps the ledger
  ledger.py            daily accounts, paired as sent and received, checked every day
  users.py             the water-user interface: roles, units, hourly-to-daily integration, the user's balance
  mapping.py           area maps between SWAT+ objects and MODFLOW 6 cells
  units.py             unit factors to the ledger's SI units
  coupling/
    modflow6.py        MODFLOW 6 through libmf6 (modflowapi): prepare, set, solve, read
    recharge.py        SWAT+ aquifer recharge -> MODFLOW 6 recharge, one-way
  chain.py             the utility chain (stub)
  rules.py             feedback rules: curtailment, dry mode, drawdown limits (stub)
  testing.py           a synthetic water user for the tests
examples/
  synthetic/           SWAT+'s Osu_1hru + a small MODFLOW 6 model + the synthetic user (the tests use it)
    basin.toml  model.py  user.toml  fetch.py  notebook.py  README.md
  plaster-creek/       planned: Plaster Creek (Kent County, Michigan) with a data center campus
tests/                 unit tests, and the one-way coupling run on the synthetic example
docs/
  design.md            this note
  prior-art.md         earlier SWAT/SWAT+ and MODFLOW couplings
  requests.md          changes asked of waterledger-models and swatplus-bmi
```

Each example folder holds:

- `basin.toml`, the config;
- `fetch.py`, which downloads its public data into a cache folder (outside git) and builds or places the model files;
- `README.md`, a short write-up: the basin, the models and their versions, calibration status, what the example shows;
- optionally a builder module for its MODFLOW 6 model and a notebook.

## The models and how each is driven

| Model | Access | Step | What Basin Ledger reads and sets |
|---|---|---|---|
| SWAT+ 62.0.1 | `swatplus-bmi` (BMI 2.0, SWAT+ in its own process, commands over standard input and output) | 1 day | reads channel flow and storage, aquifer storage, depth to water, aquifer outflow and recharge; sets point source flow and water allocation demand for the next day |
| MODFLOW 6 (6.8.2 tested) | `libmf6` through BMI/XMI, from Python with USGS `modflowapi` (in process) | 1 day (one TDIS step) | sets recharge (RCH `RECHARGE`) and well rates (WEL `Q`) between prepare and solve; reads simulated flows (`SIMVALS`), heads (`X`) |
| Water users | BMI components from `waterledger-models` (in process) | the component's own (hourly for `CoolingWaterBmi`) | sets weather inputs and limits; reads withdrawal, consumption, return, gain, constituents, temperature, power |

**The day.** For day *d* the driver:

1. steps each water user through the day (24 hourly steps) and integrates its volumes;
2. routes each user's withdrawal and return. Built: a well in MODFLOW 6, or an outfall account. Planned: the utility
   chain and SWAT+ point sources and places of use;
3. runs SWAT+ for day *d* (`update()`); values read at the pause that follows are day *d*'s;
4. prepares MODFLOW 6's step for day *d*. It sets day *d*'s recharge from SWAT+ and the day's well pumping, then
   solves;
5. enters both sides of every transfer in the ledger and checks them.

**A MODFLOW 6 detail.** MODFLOW 6.5 and later keep a package's input in named arrays (`RCH/RECHARGE`, `WEL/Q`) and
copy them into `BOUND` when the step is prepared. A value written to `BOUND`, as in the examples in Hughes et al.
(2022), is overwritten before the solve. Basin Ledger sets the named arrays, after `prepare_time_step` and before
`do_time_step`. List packages are filled only when a period is read, so entries are found after the first prepare.
The step length is known only after prepare, so the one-day check happens then. libmf6 holds one simulation per
process. Runs can follow one another in a process but can't overlap, so scenarios run in separate processes.

## Water users

A water user is any BMI component that reports its water through these roles. A component that uses other names is
mapped role by role in the example's config (`variables = {withdrawal = "...", gain = "..."}`). Nothing in the engine
knows what kind of user it is.

| Role | Common variable name | Units | Required |
|---|---|---|---|
| withdrawal | `water_user_water__withdrawal_volume_flux` | m3 s-1 | yes |
| gain | `water_user_water__gain_volume_flux` | m3 s-1 | no: water entering by other ways (condensate from air, ore moisture, water made in a process) |
| consumption | `water_user_water__consumption_volume_flux` | m3 s-1 | yes, if any: evaporated, or leaving in product or waste |
| return | `water_user_water__return_volume_flux` | m3 s-1 | yes, if any: discharged to a sewer or an outfall |
| storage | `water_user_water__volume` | m3 | no: water held on site (ponds, tailings) |
| temperature | `water_user_return_water__temperature` | degC | no |
| constituents | `water_user_return_water_<name>__mass_flux` | kg s-1 | no: one per constituent, in the return |
| power | `water_user__electric_power` | MW | no: facility electricity, for the power side of a trade-off |
| limit (input) | `water_user_water__withdrawal_volume_flux_limit` | m3 s-1 | no: a cap a feedback rule sets; infinity means none |

Units are converted on reading (`units.py`): m3 d-1, L s-1, kW and kg d-1 are accepted, and anything else is
refused. Names follow the [CSDMS Standard Names](https://csdms.colorado.edu/wiki/CSDMS_Standard_Names) pattern.

**The user's balance.** Every step, withdrawal + gain = consumption + return + change in storage. The interface checks
it on each step, to a relative 1e-9, and refuses a component that doesn't close. `CoolingWaterBmi` closes with its
condensate mapped as a gain.

**Hourly to daily.** The hydrologic models step daily, and users usually step hourly. `WaterUser.advance_day(d)` steps
the component from wherever it is to the end of day *d*, setting its inputs before each step (hourly weather from the
shared forcing, limits from the rules). After each step it reads the rates, which describe the step just ended, and
multiplies by the step length:

- volumes (m3) are summed: the daily models get the day's total, or the day's mean rate as total / 86,400 s;
- constituent masses (kg) are summed. The day's concentration in the return is mass / return volume, never a mean of
  hourly concentrations;
- return temperature is flow-weighted: the sum of return volume × temperature, over the return volume (a heat
  balance);
- electricity is summed to MWh.

A component with a daily or other step works the same way. The driver only asks it to reach the end of the day.

**Routing.** Each user's config names where its withdrawal comes from and where its return goes:

- `well:<name>`: pumped from a MODFLOW 6 well (built);
- `outfall:<name>`: a return entered in the ledger only (built);
- planned:
  - `swat:place_of_use:<name>`: a SWAT+ water allocation demand, taken from a channel, a reservoir or SWAT+'s aquifer;
  - `swat:point_source:<name>`: a SWAT+ daily point source, positive;
  - `utility:<name>`: the utility chain.

**The utility chain** (planned, `chain.py`) is accounting, not a model:

- **source:** the utility's withdrawal, split among its wells, intakes, and sources outside the basin;
- **distribution losses;**
- **users:** every water user, plus the system's existing demand, as a daily series;
- **sewer:** with inflow and infiltration;
- **wastewater plant;**
- **outfall:** a SWAT+ point source, with loads and temperature.

Each link is a ledger pair. A user on municipal supply is routed `utility:<system>`, and the chain places the water.
A user with its own wells or intake is routed directly.

## Geography: NextGen

The spatial frame is NOAA's [NextGen hydrofabric](https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/index.html)
(v2.2): catchments (`cat-`), flowpaths (`wb-`) and nexuses (`nex-`). Results are keyed to those ids, so they line up
with the National Water Model and with anything else on that frame.

- **SWAT+** is built on the hydrofabric: one subbasin per catchment, one channel per flowpath. A builder for that is
  planned; SWAT+'s usual tools (QSWAT+, SWAT+ Editor) delineate their own watersheds. The example records the
  hydrofabric version and each SWAT+ object's id.
- **MODFLOW 6** keeps its own grid. Maps tie it to the hydrofabric: catchments and HRUs to cells by area of overlap,
  and flowpaths to river or stream cells by length in each cell. Maps are made in GIS (flopy's `GridIntersect` on the
  hydrofabric layers), written to CSV and read through config, so coupling code never sees geometry.
- **Water users** are points, and the utility chain places their water.

NextGen's own framework (ngen) runs one model per catchment. SWAT+ and MODFLOW 6 each solve their whole domain at
once, so Basin Ledger uses NextGen's geography, not its runtime. A Basin Ledger result can be handed to ngen at a
nexus.

## Forcing: AORC

All models use one weather source. NOAA's Analysis of Record for Calibration (AORC) is the natural pick: hourly, about
1 km, 1979 onward, the forcing NextGen and the National Water Model are calibrated with, and open on AWS. It is
chosen for this engine on its own merits, independently of Water Ledger's weather (ERA5).

- SWAT+ gets daily precipitation, minimum and maximum temperature, solar radiation, humidity and wind, aggregated from
  AORC over each catchment, in SWAT+'s weather files.
- Water users get hourly air temperature and relative humidity (from AORC's specific humidity, temperature and
  pressure) at their site, through the `inputs` hook.
- MODFLOW 6 needs weather only if an example uses its ET or unsaturated zone packages.

## The MODFLOW 6 coupling

Prior work is summarized in `docs/prior-art.md`. Every published SWAT or SWAT+ coupling with MODFLOW compiles
MODFLOW-NWT into one executable, or uses SWAT+'s own gwflow module. The only SWAT+ to MODFLOW 6 coupling in Python
we found is a 2026 conference abstract (Nikiel and Żurek), with no code. Basin Ledger's coupling differs in four
ways:

- the two models stay separate programs, each unmodified;
- they exchange water through standard interfaces;
- every exchange is checked by a ledger;
- the coupling is general over places and water users.

**One-way: recharge and wells (built).**

- After SWAT+'s day, the driver reads each aquifer's recharge (`soil_water_table__recharge_rate`, m s-1).
- The area map spreads it over cells. A cell's rate is the sum over the objects covering it of rate × overlap area,
  divided by the cell's area. Volume is kept exactly.
- The rate goes into MODFLOW 6's recharge package for the same day.
- Users' well withdrawals are summed per well and set in the well package.
- In the ledger, recharge sent (rate × mapped area) equals recharge received (RCH `SIMVALS`), and well pumping
  requested equals pumped, every day.

In one-way mode SWAT+ keeps its own aquifer and baseflow, and MODFLOW 6 is a reading of what the same recharge does to
heads and to stream leakage. Each model keeps its own calibration. This is enough to show drawdown at a utility's wells
and when depletion reaches a stream. It is not enough to change the streamflow SWAT+ reports.

**Recharge from HRUs.** SWAT+'s aquifer is lumped per subbasin, so mapping aquifers to cells spreads recharge evenly
within each subbasin. Bailey et al. (2025) map HRU recharge to cells by area. That needs HRU percolation through BMI,
which swatplus-bmi doesn't expose yet (`docs/requests.md`). The map format already takes any object type.

**Two-way: stream-aquifer exchange (designed, not built).** MODFLOW 6 computes the exchange between streams and the
aquifer (RIV, or SFR for routed streams), and that exchange replaces SWAT+'s aquifer return flow.

- **No double counting.** SWAT+'s aquifer must stop returning water once MODFLOW 6 does.
  - This is done in the example's SWAT+ inputs, not in code: `flo_min` and `revap_min` set above any reachable
    storage, and `rchg_dp` zero. SWAT+'s aquifer then only receives recharge and holds it.
  - The ledger counts SWAT+'s aquifer storage change as transferred to MODFLOW 6.
  - A test checks that SWAT+'s aquifer outflow (`aquifer_water__volume_outflow_rate`) is zero on every day.
  - Recharge is counted once, in MODFLOW 6.
- **Gaining reaches.** Leakage to a stream on day *d* is summed per SWAT+ channel through the flowpath-to-cell map. It
  enters that channel as a positive point source on day *d*+1.
- **Losing reaches.** Leakage from a stream on day *d* is taken from the channel on day *d*+1 as a water allocation
  demand. A negative point source would not work: SWAT+ 62.0.1 records a negative point source in full even when the
  channel can't supply it. If the channel can't supply the demand, the shortfall is entered in the ledger and
  MODFLOW 6's stage for that reach is lowered for the next day.
- **Stage.** MODFLOW 6's river stage for day *d* comes from SWAT+'s channel on day *d*−1. That needs channel depth
  through BMI, which is a request to swatplus-bmi.
- **Timing.** The exchange is explicit with a one-day lag. Volume is conserved exactly (ledger pairs); timing shifts by
  a day, which is small against the time scales of groundwater response. Iterating within the day by branching SWAT+
  is possible but costs a SWAT+ day per iteration. It will be tried if the lag matters for an example's question.
- **Mapping.** Channels map to cells by length (`object, layer, row, col, length_m`). Conductance comes from the
  MODFLOW 6 model, not from the map.

**Wells.** A utility's wells are MODFLOW 6 wells named in the config, each by cell. A well screened over several layers
will use the MAW package. The chain splits a utility's groundwater withdrawal among its wells by share or by capacity.
A drawdown-limit rule reads the head at a well's cell or at a sentinel cell.

## Balances: quantity and quality

The ledger enters, every day, each transfer as sent and as received, plus each component's own balance terms.

- **Held now, by tests on the synthetic example:**
  - recharge sent = received, against SWAT+'s printed aquifer recharge and MODFLOW 6's budget file;
  - well pumping requested = pumped = withdrawn by users;
  - each user's withdrawal + gain = consumption + return, every hour and every day;
  - user returns = outfall volumes;
  - MODFLOW 6's budget (storage, recharge, wells, river) closes every day to 1e-7 of the gross flow.
- **Quality.** Constituents are masses (kg), never concentrations, across every transfer:
  - a user's return carries its loads (dissolved solids concentrated by evaporation, a cooling tower's blowdown) to the
    outfall;
  - the outfall becomes a SWAT+ point source with those loads;
  - temperature is carried as heat (volume × temperature) and becomes a temperature only at the receiving water.
  - Needs: point source loads settable through swatplus-bmi, and intake concentrations as an input to user components
    (both in `docs/requests.md`).
- **Whole basin.** For each example, a basin-wide check closes over the run:
  - precipitation = evapotranspiration + streamflow out + change in soil, aquifer and channel storage + net user
    consumption + transfers out of the basin;
  - the same for each constituent's mass, from SWAT+'s and MODFLOW 6's own budgets plus the ledger.

## Calibration

An example is only as good as its models' calibration. Every example records its calibration and validation, and an
uncalibrated example is labeled a screening run.

- **One-way couplings** keep each model's own calibration:
  - SWAT+ against streamflow (USGS gages) and, where available, water quality;
  - MODFLOW 6 against heads (USGS and state well records) and base flow.
- **With feedback** (two-way exchange, curtailment, drawdown limits), the models are calibrated jointly:
  - the prior comes from the individual calibrations;
  - [PEST++ IES](https://github.com/usgs/pestpp) runs with Basin Ledger's driver as the forward model;
  - the parameters are those the feedback touches: streambed conductance, aquifer hydraulic conductivity and specific
    yield near streams, and SWAT+'s percolation and channel parameters;
  - the observations are streamflow (low flows weighted), heads, and gage-based base flow.
  - The forward model is one command (`python -m basinledger run basin.toml`, planned) that writes the observed
    quantities to files PEST++ reads. IES gives an ensemble, so results can carry its spread.
- Calibration runs are parallel by nature. On a shared machine they're held to the cores Andrew allows.

## Scenarios from a shared warm-up

A study runs a baseline and several scenarios (no user; the user as proposed; with curtailment; dry cooling; another
source). All of them start from one warm-up:

- **SWAT+:** `branch()` copies the paused SWAT+ process with fork (Mac, Linux), and `save_state()` writes it to a
  folder (any platform). Both are exact (swatplus-bmi's tests).
- **MODFLOW 6:** its state is its heads, plus the stages and storages of advanced packages (SFR, MAW, UZF) if used.
  At the end of the warm-up the driver saves heads (`X`) and those states. Each scenario starts a new MODFLOW 6
  process from them: a TDIS beginning on the branch day, the saved heads as initial conditions. A test will check that
  a restarted run equals the unbroken run to solver tolerance.
- **Water users:** a component's state, if any, is saved through `get_state`/`set_state` where the component offers
  them (CSDMS bmi PR #112). `CoolingWaterBmi` keeps no state between hours.
- **Driver:** the ledger and the rules' memory are saved with the rest.

Scenarios then run in parallel, each in its own process.

## Examples and private studies

- **Synthetic** (`examples/synthetic`, built): SWAT+'s bundled Osu_1hru project (10 ha, 2010–2023) supplies a daily
  recharge rate, spread over a 41 × 41 MODFLOW 6 grid of 50 m cells with a river along one edge. The synthetic user
  pumps one well. It exists for the tests and the notebook. Its places and numbers mean nothing.
- **Plaster Creek** (`examples/plaster-creek`, planned): Plaster Creek in Kent County, Michigan, with a data center
  campus.
  - **Models:** SWAT+ on the hydrofabric catchments; MODFLOW 6 cut from a regional model; `CoolingWaterBmi` for the
    campus; the utility chain for its supply.
  - **The groundwater model's starting point:** USGS's regional Lake Michigan Basin model (Feinstein et al., 2010) is
    SEAWAT-2000/MODFLOW-2000, 20 layers with about 1.5 km inner cells. The MODFLOW-NWT inset models derived from it
    are archived (doi:10.5066/F76D5R5V). Either can be converted to MODFLOW 6 with flopy and refined around the basin.
    The model's own files for 2010 weren't found in a data release; this needs checking with USGS.
  - **Calibration data:** USGS streamflow on Plaster Creek (gage to be confirmed) and Michigan well records. The
    Plaster Creek TMDL record (E. coli, sediment and biota) gives water quality.
- **Private studies** live in the private `northline` repository (`studies/<name>/`), never here. A study:
  - depends on `basinledger` at a pinned version;
  - follows the example layout (`basin.toml`, `fetch.py`, a write-up), with client data in its own folders under the
    client's confidentiality terms;
  - runs the same engine, so a result can be reproduced from its config and its data.

  Anything a study needs from the engine is added here first, generally, with a test on the synthetic example.
  Nothing from a client study comes back into this repository or into Water Ledger.

## What's next

1. The driver's command line and run outputs (daily tables per account, heads at named cells), and the utility chain
   with its ledger pairs.
2. `CoolingWaterBmi` limit and dry-mode inputs (a request to `waterledger-models`), then the rules: curtailment,
   dry mode, drawdown limit.
3. Surface routes through SWAT+: water allocation demand for intakes, point sources for outfalls, with loads.
4. Two-way stream-aquifer exchange (RIV, then SFR), with the SWAT+ aquifer set to pass recharge through.
5. MODFLOW 6 restart from saved heads for scenarios, and the test that restarts match unbroken runs.
6. AORC forcing for SWAT+ and the users; a SWAT+ project builder on the hydrofabric.
7. Plaster Creek as the first public example, then PEST++ IES with the driver as the forward model.

## References

- Bailey, R.T., Abbas, S., Arnold, J.G., White, M.J., 2025. SWAT+MODFLOW: a new hydrologic model for simulating
  surface–subsurface flow in managed watersheds. Geosci. Model Dev. 18, 5681–5697.
  https://doi.org/10.5194/gmd-18-5681-2025
- Feinstein, D.T., Hunt, R.J., Reeves, H.W., 2010. Regional groundwater-flow model of the Lake Michigan Basin in
  support of Great Lakes Basin water availability and use studies. USGS SIR 2010-5109.
  https://pubs.usgs.gov/sir/2010/5109/
- Hughes, J.D., Russcher, M.J., Langevin, C.D., Morway, E.D., McDonald, R.R., 2022. The MODFLOW Application Programming
  Interface for simulation control and software interoperability. Environ. Model. Softw. 148, 105257.
  https://doi.org/10.1016/j.envsoft.2021.105257
- Sommerlot, A., 2026. swatplus-bmi: run SWAT+ one day at a time through BMI. Zenodo.
  https://doi.org/10.5281/zenodo.23963201
- Other couplings: `docs/prior-art.md`.
