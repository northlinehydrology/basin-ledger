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

## References

- Hamilton, D.A., Sorrell, R.C., and Holtschlag, D.J., 2008, A regression model for computing index flows describing
  the median flow for the summer month of lowest flow in Michigan: U.S. Geological Survey Scientific Investigations
  Report 2008–5096.
- Hunt, B., 1999, Unsteady stream depletion from ground water pumping: Ground Water, v. 37, no. 1, p. 98–102.
- Michigan Compiled Laws, Natural Resources and Environmental Protection Act, Part 327, Great Lakes Preservation
  (MCL 324.32701 to 324.32733).
- Reeves, H.W., Hamilton, D.A., Seelbach, P.W., and Asher, A.J., 2009, Ground-water-withdrawal component of the
  Michigan water-withdrawal screening tool: U.S. Geological Survey Scientific Investigations Report 2009–5003.
