"""
ATLAS Phase 5 — ARIMA KPI Monitor
Runs ADF stationarity tests and ARIMA(2,d,2) forecasts on each of the 5 KPIs.
Fires alert if abs(pct_change from current to forecast) > 10%.
Writes results to analytics.kpi_alerts.
"""

import logging
import warnings
from pathlib import Path

import duckdb
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

_ROOT   = Path(__file__).resolve().parents[2]
DB_PATH = str(_ROOT / "data" / "atlas.duckdb")
ALERT_THRESHOLD  = 0.10   # 10% change triggers alert

KPI_COLS = [
    "weekly_friction_rate",
    "weekly_avg_nps",
    "weekly_channel_escalation_rate",
    "weekly_resolution_rate",
    "weekly_avg_episode_duration",
]

# Higher value = worse outcome for these KPIs
HIGHER_IS_WORSE = {
    "weekly_friction_rate",
    "weekly_channel_escalation_rate",
    "weekly_avg_episode_duration",
}


# ── ARIMA per KPI ──────────────────────────────────────────────────────────────
def _analyse_kpi(series: pd.Series, kpi_name: str) -> dict:
    values = series.dropna().values.astype(float)

    # Augmented Dickey-Fuller stationarity test
    adf_stat, adf_pvalue, *_ = adfuller(values, autolag="AIC")
    is_stationary = float(adf_pvalue) < 0.05
    d = 0 if is_stationary else 1

    # Fit ARIMA(2, d, 2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            fit = ARIMA(values, order=(2, d, 2)).fit()
            forecast = float(fit.forecast(steps=1)[0])
        except Exception as exc:
            log.warning(f"[{kpi_name}] ARIMA failed ({exc}); using naive forecast.")
            forecast = float(values[-1])

    current = float(values[-1])
    pct_change = (
        (forecast - current) / abs(current) * 100.0
        if abs(current) > 1e-9 else 0.0
    )
    alert_fired = abs(pct_change) > ALERT_THRESHOLD * 100

    # Direction: "worse" depends on which KPI
    if abs(pct_change) <= 1.0:
        direction = "stable"
    elif pct_change > 0:
        direction = "deteriorating" if kpi_name in HIGHER_IS_WORSE else "improving"
    else:
        direction = "improving" if kpi_name in HIGHER_IS_WORSE else "deteriorating"

    return {
        "kpi_name":       kpi_name,
        "current_value":  round(current,  6),
        "forecast_value": round(forecast, 6),
        "pct_change":     round(pct_change, 2),
        "is_stationary":  is_stationary,
        "alert_fired":    alert_fired,
        "direction":      direction,
        "adf_pvalue":     round(float(adf_pvalue), 6),
    }


# ── Print report ───────────────────────────────────────────────────────────────
def _print_report(df: pd.DataFrame) -> None:
    sep  = "=" * 96
    n_alerts = int(df["alert_fired"].sum())

    print(f"\n{sep}")
    print("  ATLAS ARIMA KPI Monitor — Forecast Alert Report")
    print(sep)
    print(
        f"  {'KPI':<35} {'Current':>10} {'Forecast':>10} "
        f"{'Change%':>8}  {'Stationary':>12}  {'Alert':>5}  Direction"
    )
    print(
        f"  {'-'*35} {'-'*10} {'-'*10} "
        f"{'-'*8}  {'-'*12}  {'-'*5}  {'-'*13}"
    )

    for _, r in df.iterrows():
        stat_tag  = f"yes p={r['adf_pvalue']:.3f}" if r["is_stationary"] else f"no  p={r['adf_pvalue']:.3f}"
        alert_tag = "*** YES" if r["alert_fired"] else "no"
        print(
            f"  {r['kpi_name']:<35} "
            f"{r['current_value']:>10.4f} "
            f"{r['forecast_value']:>10.4f} "
            f"{r['pct_change']:>+8.2f}%  "
            f"{stat_tag:>12}  "
            f"{alert_tag:>5}  "
            f"{r['direction']}"
        )

    print(f"\n  {n_alerts} alert(s) fired out of {len(df)} KPIs monitored.")
    print(f"{sep}\n")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("ATLAS Phase 5 — ARIMA KPI Monitor")
    con = duckdb.connect(DB_PATH)

    try:
        kpi_df = con.execute(
            "SELECT * FROM analytics.kpi_weekly_summary ORDER BY week_start"
        ).df()
        log.info(f"Loaded {len(kpi_df)} weeks of KPI data")

        results = []
        for col in KPI_COLS:
            log.info(f"Analysing {col} ...")
            res = _analyse_kpi(kpi_df[col], col)
            results.append(res)
            log.info(
                f"  current={res['current_value']:.4f}  "
                f"forecast={res['forecast_value']:.4f}  "
                f"pct={res['pct_change']:+.2f}%  "
                f"alert={'YES' if res['alert_fired'] else 'no'}"
            )

        alerts_df = pd.DataFrame(results)

        con.register("_kpi_alerts", alerts_df)
        con.execute(
            "CREATE OR REPLACE TABLE analytics.kpi_alerts AS SELECT * FROM _kpi_alerts"
        )
        con.unregister("_kpi_alerts")
        log.info(f"DuckDB: analytics.kpi_alerts — {len(alerts_df)} rows")

        _print_report(alerts_df)

    finally:
        con.close()

    log.info("Done.")


if __name__ == "__main__":
    main()
