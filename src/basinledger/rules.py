"""Feedback rules: decisions made each day from the models' state, applied to the next day. Not built yet.

A rule reads state at the pause between days (yesterday's flow, today's well heads) and sets limits for the coming
day. Planned rules:

- **Curtailment.** Cap a river withdrawal when yesterday's flow is below a threshold (a percentile, a pass-by flow,
  Michigan's Water Withdrawal Assessment index flow).
- **Dry mode.** Tell a cooling user to run dry (no evaporation, more electricity) on days a rule says so. Needs an
  input on the user component (see docs/requests.md).
- **Drawdown limit.** Cut a well's pumping when the head in its cell, or at a sentinel cell, falls below a limit.

Every user component that takes limits exposes ``water_user_water__withdrawal_volume_flux_limit`` (m3 s-1) as an
input; the rule sets it before the user's day is stepped. A rule is a small function, ``rule(state) -> limits``, so a
study can write its own in its example.
"""


class Rule:
    def __call__(self, state) -> dict:
        raise NotImplementedError("feedback rules are planned; see docs/design.md")
