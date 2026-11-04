"""The utility chain: source -> treatment -> users -> sewer -> treatment -> outfall. Not built yet.

The chain is accounting, not a model. It will take each user's daily withdrawal and return and place them in the
hydrologic models:

- **Source.** A share of the utility's withdrawal from each of its sources: wells (MODFLOW 6 WEL entries), a river
  intake (a SWAT+ water allocation place of use), or a source outside the basin (Lake Michigan, a wholesale supplier),
  which is only recorded.
- **Losses.** Distribution losses (non-revenue water) at a set fraction; leaks may go back to the aquifer as recharge.
- **Users.** Every water user on the system, plus the system's existing demand (a daily series from the example's data).
- **Sewer and plant.** Returns flow to the wastewater plant, with inflow and infiltration added as set.
- **Outfall.** The plant's discharge enters a SWAT+ channel as a point source the same day, with its constituent loads
  (mass) and temperature.

Each link is a ledger pair, so the chain balances by construction and the tests hold it to that.

For now the driver supports two routes directly: ``well:<name>`` (a user's withdrawal pumped from a MODFLOW 6 well) and
``outfall:<name>`` (a return entered in the ledger only).
"""


class UtilityChain:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError("the utility chain is planned; see docs/design.md")
