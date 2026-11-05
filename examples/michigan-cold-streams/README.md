# Michigan cold-stream screen

This screen picks the first basin for a cold-water study. The study asks what a groundwater-sourced campus (a data
center or another large new water user) does to a groundwater-fed trout stream's low flow and summer temperature, and
how that compares with what Michigan's Water Withdrawal Assessment Tool (WWAT) allows. The campus can be hypothetical,
placed where one plausibly could go. The first basin has to show that the coupled setup (SWAT+, MODFLOW 6, a water
user and a stream temperature calculation) finds something out, or shows the simple method is enough. The plan after
it is three to five basins, one per cold-stream setting, then statewide scenarios using a fast method checked against
those coupled basins.

This is a screen of public data, not a study result. Nothing here is calibrated.

## Shortlist

![Gaged basins scored for a first cold-stream study](screen-map.png)

1. **Dowagiac River at Sumnerville (USGS 04101800), 659 km², Cass and Van Buren Counties.** Strong on every criterion
   except temperature data.
   - **Cold water:** 102 km of cold and cold-transitional streams (46% of the basin's network) and 215 km of designated
     trout stream.
   - **Groundwater:** base flow index 0.77. Outwash covers 72% of the basin.
   - **Siting:** 67 km of 138 kV-and-up lines and 9 substations inside the basin.
   - **Irrigation:** the screen's heaviest groundwater irrigation, about 44,000 m³/d averaged over the year (county
     totals spread by area [A]). That is the comparison a campus needs.
   - **A real data center:** Hyperscale Data's Dowagiac data center, operating and expanding, with its project under
     construction (Water Ledger tracker). Its exact site and water source still need checking.
   - **Weak point, temperature data:** there's no continuous record at the gage. The Pokagon Band of Potawatomi's
     water program and EGLE have about 1,100 stream temperature results since 2010, at 19 sites, at most 27 a site
     a year. That's enough to check a seasonal pattern, not a daily calibration, unless someone has loggers.
2. **Pine River near Hoxeyville (04125460), 652 km², Lake and Wexford Counties.** The temperature anchor.
   - **Cold water:** every classified reach is cold or cold-transitional, with 420 km of designated trout stream.
   - **Groundwater:** base flow index 0.78, and Q90/Q50 of 0.81, among the steadiest flows on the list.
   - **Temperature data:** about 30 years of daily water temperature at the gage. No other candidate has a record
     this long.
   - **Representative setting:** it sits in the Newaygo outwash plain, part of the northern Lower Peninsula, which holds
     40% of the state's cold and cold-transitional stream length.
   - **Siting is thin:** 7 km of high-voltage line, no substation in the basin, and no data center activity.
3. **Rogue River near Rockford (04118500), 675 km², Kent and Newaygo Counties.** The home-turf option.
   - **Cold water and siting:** 572 km of designated trout stream, 92 km of high-voltage line and 7 substations.
   - **Data centers:** Solon Township's inquiry (and its moratorium) is in the basin. Switch's Gaines campus and other
     Grand Rapids data centers are within 15 km.
   - **Weak points:** a lower outwash share (30%) and little temperature data (108 results).
   - **Basin area:** NLDI's basin is 11% larger than USGS's 606 km², which needs checking before it's used.

**Recommendation:** the Dowagiac first, with the Pine as the second basin. The Dowagiac is where a campus,
irrigation and a trout stream already share one outwash aquifer, so a finding there means something. The Pine's
30-year record is the best test of the temperature calculation. Before committing to the Dowagiac, two checks:

- whether loggers exist (Pokagon Band, MDNR Fisheries, Trout Unlimited);
- where the Dowagiac campus is and what water it uses.

The Jordan River (175 km², 17 years of temperature at the gage) scored first but has no data center activity
nearby and is small. It's a good candidate for a later setting.

## Where Michigan's cold streams are

Of the 70,400 km of reaches in Michigan's valley segment classification (VSEC), 21,400 km are cold or
cold-transitional.

| Region | Share of cold and cold-transitional length |
|---|---|
| Northern Lower Peninsula (sections VII.x) | 40% |
| Upper Peninsula (VIII.x and IX.x) | 48% |
| Southern Lower Peninsula (VI.x) | 12% |

Segments that touch two ecoregions are counted in both, so the shares are approximate. The ecoregions with the most
cold length are:

- the Grayling outwash plain;
- the Winegar moraine;
- Cadillac;
- the Newaygo outwash plain;
- the Vanderbilt moraines.

Data center activity runs the other way: most of it is in the southern Lower Peninsula. Cold streams and
campuses overlap in southwest Michigan's outwash (the Dowagiac and Paw Paw), around Grand Rapids (the Rogue) and along
the southern edge of the northern outwash plains (the Pine, White and Little Muskegon). A statewide study should
cover both ends, the north where most of the cold water is and the south where most of the pressure is.

## The 12 highest-scoring basins

| | Basin (USGS gage) | km² | Cold share | Trout km | BFI | Temp. years at gage | WQP temp. results | Outwash share | HV km / substations | Irrigation m³/d/km² | Data centers | Ecoregion | Score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Jordan River near East Jordan (04127800) | 175 | 1.00 | 182 | 0.80 | 17 | 1 | 0.30 | 7 / 2 | 22 | none | Vanderbilt Moraines | 0.82 |
| 2 | Dowagiac River at Sumnerville (04101800) | 659 | 0.46 | 215 | 0.77 | 0 | 1,134 | 0.72 | 67 / 9 | 67 | in basin | Battle Creek Outwash Plain | 0.79 |
| 3 | Pine River near Hoxeyville (04125460) | 652 | 1.00 | 420 | 0.78 | 30 | 131 | 0.36 | 7 / 0 | 2 | none | Newago Outwash Plain | 0.75 |
| 4 | Paw Paw River at Riverside (04102500) | 1,016 | 0.51 | 353 | 0.74 | 0 | 1,145 | 0.53 | 122 / 6 | 21 | within 15 km | Southern Lake Michigan Lake Plain | 0.74 |
| 5 | Rifle River near Sterling (04142000) | 854 | 0.49 | 753 | 0.68 | 13 | 329 | 0.31 | 108 / 7 | 0 | none | Standish | 0.73 |
| 6 | White River near Whitehall (04122200) | 1,051 | 0.97 | 631 | 0.76 | 0 | 174 | 0.43 | 152 / 4 | 6 | moratorium in basin | Manistee | 0.72 |
| 7 | Boardman River above Brown Bridge Road (04126970) | 323 | 1.00 | 141 | 0.78 | 1 | 56 | 0.56 | 0 / 0 | 9 | within 15 km | Grayling Outwash Plain | 0.72 |
| 8 | Clinton River at Sterling Heights (04161820) | 811 | 0.09 | 160 | 0.70 | 30 | 557 | 0.42 | 92 / 3 | 4 | in basin | Maumee Lake Plain | 0.72 |
| 9 | Rogue River near Rockford (04118500) | 675 | 0.46 | 572 | 0.72 | 0 | 108 | 0.30 | 92 / 7 | 7 | in basin | Lansing | 0.70 |
| 10 | Little Muskegon River near Oak Grove (04121944) | 965 | 0.41 | 602 | 0.73 | 31 | 34 | 0.45 | 0 / 0 | 39 | within 15 km | Newago Outwash Plain | 0.70 |
| 11 | Platte River at Honor (04126740) | 331 | 0.67 | 87 | 0.80 | 0 | 6 | 0.77 | 4 / 2 | 1 | within 15 km | Manistee | 0.69 |
| 12 | Fish Creek near Crystal (04115265) | 97 | 1.00 | 59 | 0.74 | 0 | 1 | 0.44 | 10 / 1 | 66 | none | Lansing | 0.69 |

All 78 scored basins and every measure are in `screen.csv`; `screen.json` adds the statewide ecoregion sums and the basins left out.

The Clinton River ranks eighth on data and siting alone; its cold share is 0.09. Gage temperature "years" are the
span of the daily record, not a count of complete years.

## Method

**Units.** Each unit is a USGS streamgage with daily discharge from at least 20 years, still reporting in 2024 or
later, with a drainage area of 100 to 1,500 km² (81 gages), and its NLDI basin (80; NLDI has none for 04057814). Two
NLDI basins disagree with USGS's drainage area by more than 25% and aren't scored: Pigeon River near Vanderbilt
(04128990, 201 vs 149 km²) and Farmers Creek near Lapeer (04146000, 9 vs 143 km²). That leaves 78.
Nested basins are kept and marked in `nested_in`.

**Measures**, by criterion:

1. **Cold water:**
   - cold and cold-transitional share of VSEC stream length;
   - designated trout stream length per km² (EGLE, Fisheries Order 210).

   Both count because the two don't always agree: Augusta Creek is entirely a designated trout stream but VSEC calls
   it warm-transitional. Segments touching the basin count in full.
2. **Groundwater-fed:** base flow index by the Eckhardt filter (BFImax 0.8 [A]; the recession constant is the 90th
   percentile of recession ratios), and Q90/Q50, both from water years 1997–2025.
3. **Data:**
   - years of daily water temperature at the gage (USGS);
   - stream temperature results in the Water Quality Portal since 2010 inside the basin.

   The 20-year flow record is already a condition for entry.
4. **Aquifer:** share of the basin mapped as outwash in Farrand and Bell's (1982) Quaternary geology, plus the share of
   any coarse unit (outwash, coarse till, lacustrine sand, dune sand). The 1981 atlas's aquifer map wasn't used: its
   server's certificate chain doesn't verify from Python.
5. **Siting:** OSM power lines of 138 kV and above inside the basin, and substations of that voltage inside it. OSM
   coverage is good for transmission but not complete [A].
6. **Existing large user:** groundwater irrigation, USGS 2015 county withdrawals spread over each basin by area [A].
   Irrigation is seasonal, so summer rates are several times the annual average shown.
7. **Data center activity:** Water Ledger's public tracker (existing data centers, projects and proposals, inquiries,
   moratoria), each at its place's centroid [A]. A project's actual site can be a few kilometres away.

Basin size (100 to 1,500 km²) is a condition for entry, not part of the score.

**Score.** Each part is a percentile rank among the 78 basins or a simple step, in [0, 1]. The score is their weighted
mean:

| Part | Weight | Built from |
|---|---|---|
| cold | 2 | cold share rank 0.5, trout density rank 0.5 |
| groundwater | 1 | BFI rank 0.5, Q90/Q50 rank 0.5 |
| temperature data | 1 | gage temperature years/10 (capped at 1) × 0.6, WQP results/500 (capped) × 0.4 |
| aquifer | 1 | outwash share rank 0.6, coarse share rank 0.4 |
| siting | 1 | 1 with lines and a substation inside; 0.7 lines only; 0.4 lines within 5 km; else 0 |
| irrigation | 0.5 | irrigation per km² rank |
| data centers | 0.5 | 1 in the basin; 0.6 within 15 km; 0.3 a moratorium in the basin; else 0 |

The weights are judgment [A]. Cold water counts double because it's the question. Irrigation and data centers count
half because they are bonuses: the campus can be hypothetical. The shortlist is chosen from the top of the ranking by
reading the measures, not from the score alone.

**Not checked yet**, and needed before a basin is chosen:

- lake and impoundment share (lakes complicate MODFLOW 6);
- existing high-capacity wells from Wellogic;
- whether MDNR, tribal or watershed group temperature loggers exist;
- each campus's actual site and water source.

## Run

```bash
uv sync --group gis --group examples
uv run --group gis python examples/michigan-cold-streams/fetch.py      # public data to the cache (~45 MB)
uv run --group gis python examples/michigan-cold-streams/screen.py     # screen.csv, screen.json
uv run --group gis --group examples python examples/michigan-cold-streams/figure.py   # screen-map.png
```

`fetch.py` lists every source. It reads Water Ledger's public tracker from waterledger.org, never a private file.
