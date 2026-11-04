import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Basin Ledger: the synthetic example

    SWAT+'s bundled Osu_1hru project (2010–2023) runs one day at a time through
    [swatplus-bmi](https://doi.org/10.5281/zenodo.23963201). After each day its aquifer recharge goes into a small
    MODFLOW 6 model through libmf6: 41 × 41 cells of 50 m, a river along the west edge. A synthetic water user
    withdraws about 520 m³ a day from one well and returns 30% of it to an outfall.

    The example runs twice, with the user and without. The difference in heads is the drawdown. The difference in
    the river's gain from the aquifer is the streamflow depletion. The ledger checked every day of both runs:
    recharge sent equals recharge received, and pumping requested equals pumped.

    The places and numbers mean nothing. Osu_1hru is a 10 ha project, and its recharge rate is spread over the whole
    grid. The example exists to test the engine.
    """)
    return


@app.cell
def _():
    from pathlib import Path

    import flopy
    import matplotlib.pyplot as plt
    import numpy as np

    from basinledger.driver import Basin

    HERE = Path(__file__).resolve().parent
    CONFIG = HERE / "basin.toml"
    FIGS = HERE.parents[1] / "docs" / "figures"
    return Basin, CONFIG, FIGS, flopy, np, plt


@app.cell
def _(Basin, CONFIG, flopy):
    def run(name, users):
        b = Basin.from_config(CONFIG, run=name, users=users)
        b.run()
        table, ws, start = b.ledger.table(), b.mf6.ws, b.start
        b.finalize()
        heads = flopy.utils.HeadFile(ws / "gwf.hds").get_alldata()[:, 0]
        cbc = flopy.utils.CellBudgetFile(ws / "gwf.cbc", precision="double")
        riv = [float(d["q"].sum()) for d in cbc.get_data(text="RIV")]
        return dict(table=table, heads=heads, riv=riv, start=start)

    pumping = run("notebook-pumping", True)
    base = run("notebook-base", False)
    return base, pumping


@app.cell
def _(base, np, pumping):
    import datetime as dt

    days = len(pumping["table"]["recharge:sent"])
    dates = np.array([pumping["start"] + dt.timedelta(days=i) for i in range(days)])
    well = (20, 28)
    drawdown = base["heads"] - pumping["heads"]  # m, positive down
    pumped = pumping["table"]["well:pw1:pumped"]  # m3 d-1
    depletion = np.array(pumping["riv"]) - np.array(base["riv"])  # less water to the river, m3 d-1
    return dates, depletion, drawdown, pumped, well


@app.cell
def _(FIGS, dates, plt, pumped, pumping):
    _fig, _ax = plt.subplots(figsize=(9, 3.2))
    _ax.plot(dates, pumping["table"]["recharge:sent"], lw=0.6, color="#3b6ea5", label="recharge from SWAT+")
    _ax.plot(dates, pumped, lw=0.8, color="#c0504d", label="well pumping")
    _ax.set_ylabel("m³ per day")
    _ax.set_title("Daily recharge from SWAT+ into MODFLOW 6, and the user's pumping")
    _ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    _fig.tight_layout()
    FIGS.mkdir(parents=True, exist_ok=True)
    _fig.savefig(FIGS / "synthetic-recharge.png", dpi=150)
    _fig
    return


@app.cell
def _(FIGS, dates, drawdown, plt, well):
    _fig, (_a, _b) = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [1.7, 1]})
    _a.plot(dates, drawdown[:, well[0], well[1]], color="#c0504d", label="at the well")
    _a.plot(dates, drawdown[:, 20, 14], color="#7a7a7a", label="700 m toward the river")
    _a.set_ylabel("drawdown, m")
    _a.set_title("Drawdown over time")
    _a.legend(frameon=False)
    _im = _b.imshow(drawdown[-1], cmap="Reds", extent=(0, 2050, 0, 2050))
    _b.set_title("Drawdown at the end, m")
    _b.set_xlabel("m (river at x = 0)")
    _fig.colorbar(_im, ax=_b, shrink=0.8)
    _fig.tight_layout()
    _fig.savefig(FIGS / "synthetic-drawdown.png", dpi=150)
    _fig
    return


@app.cell
def _(FIGS, dates, depletion, np, plt, pumped):
    _k = 30
    _mean = lambda x: np.convolve(x, np.ones(_k) / _k, "valid")
    _fig, _ax = plt.subplots(figsize=(9, 3.2))
    _ax.plot(dates[_k - 1:], _mean(pumped), color="#c0504d", label="pumping")
    _ax.plot(dates[_k - 1:], _mean(depletion), color="#3b6ea5", label="streamflow depletion")
    _ax.set_ylim(bottom=0)
    _ax.set_ylabel("m³ per day")
    _ax.set_title("Pumping and the streamflow depletion it causes (30-day means)")
    _ax.legend(frameon=False, loc="lower right")
    _fig.tight_layout()
    _fig.savefig(FIGS / "synthetic-depletion.png", dpi=150)
    _fig
    return


@app.cell(hide_code=True)
def _(depletion, drawdown, mo, pumped, pumping, well):
    t = pumping["table"]
    mo.md(f"""
    **The ledger, whole run.** Recharge sent {t['recharge:sent'].sum():,.0f} m³, received
    {t['recharge:received'].sum():,.0f} m³. Withdrawn by the user {t['user:plant:withdrawal'].sum():,.0f} m³,
    pumped {pumped.sum():,.0f} m³. Consumed {t['user:plant:consumption'].sum():,.0f} m³, returned to the outfall
    {t['outfall:creek'].sum():,.0f} m³.

    **The aquifer.** Drawdown at the well at the end: {drawdown[-1, well[0], well[1]]:.2f} m. Over the last year,
    streamflow depletion was {depletion[-365:].sum() / pumped[-365:].sum():.0%} of pumping, against
    {depletion[:365].sum() / pumped[:365].sum():.0%} in the first.
    """)
    return


if __name__ == "__main__":
    app.run()
