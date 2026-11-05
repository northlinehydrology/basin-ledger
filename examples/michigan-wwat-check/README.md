# Michigan WWAT check

## Summary

A statewide screen for where a high-capacity well that passes Michigan's Water Withdrawal Assessment Tool (WWAT) is
most likely to reduce a cold stream's flow or warm it anyway. It builds on the
[cold-stream screen](../michigan-cold-streams/) and uses the same 78 gaged basins and area check. It uses public data
only and runs no models. This is step 1 of 3: data and ranking. Step 2 checks the WWAT against dry-year arithmetic at
the candidates. Step 3 runs coupled models at two or three of them.

## Question

Does the WWAT hold up where it is most likely to fail?

The test is two-sided. If the WWAT's limits hold at the places ranked most likely to fail, that is a result. If they
miss there, the conditions under which they miss are a result. The screen extends the state's tool. It does not
replace it.

The WWAT's limits are fractions of the index flow, the median flow of the lowest summer month (MCL 324.32701(1)(x)).
Groundwater withdrawals are evaluated with an analytical depletion model after five years of pumping (Reeves and
others, 2009). We look at five ways a withdrawal that passes could still harm a cold stream:

1. **Median summer only.** The limits scale with the median summer month. In a dry summer the same depletion is a
   larger share of the flow.
2. **Delay.** The depletion model is read at five years. Where depletion is still rising then, the tool sees less
   than the long-run loss.
3. **Registered and actual use.** The tool debits registered withdrawals. Irrigation and other use that is pumped but
   not registered, or registered below what is pumped, is not debited.
4. **Municipal exemption.** A campus served by a community supply is not screened as its own withdrawal. A
   community supply's withdrawals are exempt from Part 327's withdrawal permit (MCL 324.32723(13)(a)).
5. **Flow, not temperature.** The limits come from fish responses to flow loss. Warming from lost groundwater inflow
   is not modeled. Cold-transitional streams are the most sensitive to it.

A sixth path, water taken from one stream and returned to another by a utility, is not scored. Public data have no
crosswalk from community supplies to the wastewater plants that serve them.

## Rule for choosing places

Written before any basin was scored. It is not changed after results are seen. A change, if one is needed, is
recorded here with its date and reason.

- **Basins.** The 78 basins scored by the cold-stream screen, with the same area check.
- **Eligible.** At least a quarter of the basin's WWAT stream length is a cold or cold-transitional type.
- **Scores.** Each of the five paths gets a measure per basin (below). Each measure is turned into a percentile rank
  among eligible basins, from 0 (least likely to fail on that path) to 1 (most likely).
- **Candidates.** A basin is a candidate if it ranks in the top quarter on at least two of the five scores.
  Candidates are ordered by the number of top-quarter scores, then by the mean of the five ranks.
- **Step 2 set.** The top five candidates, and two controls: the two eligible basins with the lowest mean rank.

Added Nov 5, 2026, after the first run. At three eligible basins (Boardman, Iron, Pine at High School Bridge) the
layer gives the gage's segment no zone lines (see WWAT layer below), so measure 1 is missing. A missing measure is
left unranked and the mean rank is taken over the measures present. Candidates and controls must have all five,
because step 2 needs measure 1 at every basin it checks.

## Measures

1. **Median summer only.** The largest depletion that stays out of Zone D at the gage's WWAT segment, as a share of
   the gage's 1-in-10 dry summer flow. Dry summer flow is the 10th percentile, over water years 1997–2025, of each
   year's lowest July, August or September mean flow.
2. **Delay.** One minus the share of long-run depletion that the WWAT's own groundwater model reaches at five years.
   It uses Hunt (1999) with the layer's transmissivity and streambed values, the tool's storage coefficient of 0.01,
   and a well 805 m (half a mile) from the stream [A]. It is the length-weighted median over the basin's WWAT
   segments. Outwash share is shown beside it.
3. **Registered and actual use.** Groundwater irrigation per km² (USGS 2015, county totals spread by area).
4. **Municipal exemption.** Half the rank of the summed pump capacity of active community supply wells in the basin
   (EGLE Wellogic, Type I), and half the cold-stream screen's tracker part (Water Ledger records in or within 15 km
   of the basin).
5. **Flow, not temperature.** Cold-transitional share of the basin's WWAT stream length.

Results are keyed to the USGS gage, its NHDPlus COMID and its NextGen hydrofabric flowpath and nexus (v2.2).

Two more measures are recorded but not scored. They were added after the rule was written: the length of the
basin's WWAT segments with no zone lines, and the share of its WWAT length where a bedrock well passes without a
depletion estimate (bedrock categories −1 and 1; Reeves and others, 2009, table 1).

## Results

Of the 78 basins, 30 are eligible and 13 are candidates. The step 2 set:

| Basin (USGS gage) | NextGen flowpath | Median summer | Delay | Use | Municipal | Temperature | Top quarter |
|---|---|---|---|---|---|---|---|
| Clam River at Vogel Center (04121300) | wb-658385 | 0.85 | 0.03 | 0.76 | 0.83 | 0.62 | 3 |
| Black River near Bessemer (04031000) | wb-647466 | 0.96 | 0.97 | 0.07 | 0.17 | 0.79 | 3 |
| Little Muskegon River near Oak Grove (04121944) | wb-658600 | 0.65 | 0.24 | 0.93 | 0.90 | 0.59 | 2 |
| Rabbit River near Hopkins (04108600) | wb-646089 | 0.81 | 0.55 | 0.69 | 0.86 | 0.09 | 2 |
| Pine River near Rudyard (04127917) | wb-660051 | 0.73 | 0.83 | 0.34 | 0.17 | 0.83 | 2 |
| Control: Sturgeon River near Nahma Junction (04057510) | wb-644746 | 0.88 | 0.07 | 0.28 | 0.17 | 0.38 | 1 |
| Control: Middle Branch Escanaba River at Humboldt (04057800) | wb-654919 | 0.31 | 0.48 | 0.07 | 0.17 | 0.93 | 1 |

The other eight candidates, in order: Paw Paw, Rogue, Fish Creek, West Branch Ontonagon, Dowagiac, Au Train, Jordan
and Silver. `candidates.csv` has every basin's measures, scores and hydrofabric ids.

What drives the scores:

- **Median summer only.** The share of the 1-in-10 dry summer flow that a withdrawal at the Zone D boundary would
  take ranges from under 1% to 86% at eligible gages. The 1-in-10 dry summer flow is 25% to 92% of the gage's
  index flow. The largest shares are where the layer's index flow is high: at the Black, West Branch Ontonagon,
  Silver and Clam gages it is 1.7 to 2.5 times the gage's index flow for 1997–2025. The West Branch Ontonagon also
  has the lowest dry summer (25% of index flow). Where the gage's segment is cold-transitional (Rogue, Dowagiac,
  Au Train, White, Sturgeon at Wolverine) the Zone D boundary is 2% to 4% of index flow, and a passing withdrawal
  takes 2% or less of the dry summer flow.
- **Delay.** In the tool's own depletion model, a well half a mile from the stream reaches 57% to 93% of its
  long-run depletion after five years (median 87%). The Jordan is lowest. The basins rank almost the same with the
  well a quarter mile away (rank correlation 0.93) or a mile away (0.96).
- **Registered and actual use.** Groundwater irrigation is highest in the southwest and central Lower Peninsula
  (Dowagiac, Fish Creek, Little Muskegon) and near zero in the Upper Peninsula.
- **Municipal exemption.** Community supply wells in eligible basins total up to 14,600 gal/min of pump capacity
  (Paw Paw, 28 systems). The Rogue and Dowagiac also have tracker records inside the basin.
- **Flow, not temperature.** Cold-transitional streams are 0% to 100% of eligible basins' WWAT length.

## WWAT layer

`layer-check.json` has the numbers below.

- **Vintage.** The only public copy of the stream layer we found is the state's Water_Withdrawal map service, layer
  3, dated 12/22/2014, with VERSION 10 on every segment. The EGLE open data services we searched have no copy. The
  online tool may run on newer values.
- **Units.** Index flow (QE50) is in ft³/s. At 42 gages in Hamilton and others (2008), the layer's index flow at the
  gage's segment, scaled by drainage area, has a median of 1.06 times the report's gage value (10th to 90th
  percentile 0.65 to 2.08). The layer's values are the regression estimates, not the gage records.
- **Cutoffs.** On 99.95% of segments, each zone cutoff in the layer equals half of the zone line times index flow,
  in gal/min. The tool appears to screen against half the index flow. We have not confirmed this in Hamilton and
  Seelbach (2011), which we could not retrieve. Shoreline segments have a fixed cutoff of 1,440 gal/min.
- **Zone lines.** The layer's Zone D boundary, as a fraction of index flow, is 0.20 for cold streams, 0.21 for cold
  small rivers, 0.04, 0.02 and 0.03 for cold-transitional streams, small rivers and large rivers, and 0.17 to 0.25
  for cool and warm types. These are the layer's values. Part 327 defines the zones by fish response, not by
  fraction of index flow (MCL 324.32701(1)(tt) to (ww)).
- **No zone lines.** 163 segments, 161 of them cold streams and cold small rivers, have 99999 for every zone line.
  They include stretches of the Au Sable, Manistee, Pere Marquette, Boardman, Pigeon and Baldwin. We don't know
  what the tool does there. This is a question for EGLE, or a test of the online tool, before step 2.

## Limitations

- Measures 1 and 2 are taken at the gage and from the layer's segment values. A withdrawal on a headwater tributary
  meets that tributary's index flow and aquifer values, not the gage's.
- Gages are matched to WWAT segments by drainage area, river name and distance. 70 of 78 gages have a match. Three
  matched segments have no name in the layer. The South Branch Flint gage matched a North Branch Flint segment. Of
  these, only the Pine at High School Bridge is eligible, and its segment has no zone lines.
- Dry summer flow is from water years 1997–2025. The report's index flows are from records through 2005.
- The delay measure is the tool's own model run longer. It doesn't say how real aquifers respond.
- Irrigation is county-level. We found no public site-level registered withdrawals, so measure 3 is a proxy.
- Wellogic pump capacity is what was installed, not what is pumped. Some status fields are blank and are kept.
- Out-of-basin return is not scored.
- The percentile ranks are relative to these 30 basins. A basin low on every score is not shown to be safe.

## Run

```bash
uv run --group gis python examples/michigan-cold-streams/fetch.py    # if not run already
uv run --group gis python examples/michigan-cold-streams/screen.py
uv run --group gis python examples/michigan-wwat-check/fetch.py      # WWAT layer and community wells (~16 MB)
uv run --group gis python examples/michigan-wwat-check/screen.py     # candidates.csv, layer-check.json
```

NextGen ids come from a local copy of the v2.2 hydrofabric (`$HYDROFABRIC`). Without one the ids are left blank.

## References

- Hamilton, D.A., and Seelbach, P.W., 2011, Michigan's water withdrawal assessment process and internet screening
  tool: Michigan Department of Natural Resources, Fisheries Special Report 55. Cited, not retrieved.
- Hamilton, D.A., Sorrell, R.C., and Holtschlag, D.J., 2008, A regression model for computing index flows describing
  the median flow for the summer month of lowest flow in Michigan: U.S. Geological Survey Scientific Investigations
  Report 2008–5096.
- Hunt, B., 1999, Unsteady stream depletion from ground water pumping: Ground Water, v. 37, no. 1, p. 98–102.
- Michigan Compiled Laws, Natural Resources and Environmental Protection Act, Part 327, Great Lakes Preservation
  (MCL 324.32701 to 324.32733).
- Reeves, H.W., Hamilton, D.A., Seelbach, P.W., and Asher, A.J., 2009, Ground-water-withdrawal component of the
  Michigan water-withdrawal screening tool: U.S. Geological Survey Scientific Investigations Report 2009–5003.
