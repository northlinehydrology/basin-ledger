# Plaster Creek (planned)

The first public example: Plaster Creek, a tributary of the Grand River in Kent County, Michigan (about 58 square
miles), with a data center campus as the water user. Not built yet. Plan (`docs/design.md`, Examples):

- SWAT+ on the NextGen hydrofabric catchments, forced with AORC;
- MODFLOW 6 cut from USGS's Lake Michigan Basin model or its MODFLOW-NWT insets, converted with flopy;
- `CoolingWaterBmi` from `waterledger-models` for the campus, routed through the utility chain;
- calibration against USGS streamflow and Michigan well records, recorded here with validation.

Public data only. A client study in this basin would be a separate private example in the northline repository.
