"""
ATLAS Phase 5 — Alert Dispatcher
Reads analytics.kpi_alerts, prints formatted alerts for fired ones,
and writes all alerts to data/processed/atlas_alerts.log.
"""

import os
import logging
from pathlib import Path
from datetime import datetime

import duckdb
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DB_PATH  = os.getenv("DB_PATH", "data/atlas.duckdb")
LOG_FILE = Path("data/processed/atlas_alerts.log")


def _format_alert_line(r: pd.Series) -> str:
    return (
        f"ATLAS ALERT | {r['kpi_name']} | "
        f"Current: {r['current_value']:.4f} -> "
        f"Forecast: {r['forecast_value']:.4f} | "
        f"Change: {r['pct_change']:+.2f}% ({r['direction']})"
    )


def _format_info_line(r: pd.Series) -> str:
    return (
        f"ATLAS INFO  | {r['kpi_name']} | "
        f"Current: {r['current_value']:.4f} -> "
        f"Forecast: {r['forecast_value']:.4f} | "
        f"Change: {r['pct_change']:+.2f}% ({r['direction']}) | "
        f"ADF p={r['adf_pvalue']:.4f}"
    )


def dispatch(df: pd.DataFrame) -> None:
    sep = "=" * 80
    fired = df[df["alert_fired"] == True]
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Console output ────────────────────────────────────────────────────────
    print(f"\n{sep}")
    print(f"  ATLAS Alert Dispatcher  [{run_ts}]")
    print(sep)

    if fired.empty:
        print("  No alerts fired — all KPIs within threshold.")
    else:
        print(f"  *** {len(fired)} ALERT(S) FIRED ***\n")
        for _, r in fired.iterrows():
            print(f"  {_format_alert_line(r)}")

    print(f"\n  KPI Status Summary:")
    print(
        f"  {'KPI':<35} {'Alert':>5}  {'Direction':<15} {'Change%':>8}"
    )
    print(f"  {'-'*35} {'-'*5}  {'-'*15} {'-'*8}")
    for _, r in df.iterrows():
        tag = "YES **" if r["alert_fired"] else "no"
        print(
            f"  {r['kpi_name']:<35} {tag:>5}  "
            f"{r['direction']:<15} {r['pct_change']:>+8.2f}%"
        )

    total  = len(df)
    n_fire = len(fired)
    print(f"\n  Summary: {n_fire} alert(s) fired out of {total} KPIs monitored.")
    print(f"{sep}\n")

    # ── Log file output ───────────────────────────────────────────────────────
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"\n{'='*80}\n")
        fh.write(f"ATLAS Alert Run — {run_ts}\n")
        fh.write(f"{'='*80}\n")
        for _, r in df.iterrows():
            if r["alert_fired"]:
                fh.write(_format_alert_line(r) + "\n")
            else:
                fh.write(_format_info_line(r) + "\n")
        fh.write(f"\nSummary: {n_fire}/{total} KPIs fired alerts.\n")

    log.info(f"Alert log written: {LOG_FILE}  ({n_fire} alerts)")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("ATLAS Phase 5 — Alert Dispatcher")
    con = duckdb.connect(DB_PATH)

    try:
        df = con.execute("SELECT * FROM analytics.kpi_alerts ORDER BY kpi_name").df()
        if df.empty:
            log.error("analytics.kpi_alerts is empty — run kpi_arima_monitor.py first.")
            return
        log.info(f"Loaded {len(df)} KPI alert records")
        dispatch(df)
    finally:
        con.close()

    log.info("Done.")


if __name__ == "__main__":
    main()
