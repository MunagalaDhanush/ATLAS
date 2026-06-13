"""
ATLAS Phase 5 — KPI Weekly Aggregator
Queries customer_journeys and nps_surveys, computes 5 weekly KPIs,
overlays AR(1) noise + trend to create non-trivial time-series for ARIMA,
and writes analytics.kpi_weekly_summary.
"""

import logging
from pathlib import Path

import numpy as np
import duckdb
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

_ROOT   = Path(__file__).resolve().parents[2]
DB_PATH = str(_ROOT / "data" / "atlas.duckdb")
OUT_CSV = _ROOT / "data" / "processed" / "kpi_weekly_summary.csv"


# ── Noise helper ───────────────────────────────────────────────────────────────
def _ar1_noise(n: int, std: float, phi: float = 0.55, seed: int = 42) -> np.ndarray:
    """AR(1) noise so each KPI series has realistic temporal autocorrelation."""
    rng = np.random.default_rng(seed)
    eps = rng.normal(0, std, n)
    out = np.zeros(n)
    out[0] = eps[0]
    for i in range(1, n):
        out[i] = phi * out[i - 1] + eps[i]
    return out


# ── Raw DuckDB queries ─────────────────────────────────────────────────────────
def _episode_kpis(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""
        SELECT
            DATE_TRUNC('week', episode_start)                                               AS week_start,
            COUNT(*)                                                                         AS total_episodes,
            SUM(CASE WHEN is_friction_episode THEN 1 ELSE 0 END)                            AS friction_ep,
            AVG(CASE WHEN distinct_channels >= 2 THEN 1.0 ELSE 0.0 END)                    AS raw_escalation_rate,
            SUM(CASE WHEN is_friction_episode AND eventually_resolved THEN 1.0 ELSE 0.0 END)
              / NULLIF(SUM(CASE WHEN is_friction_episode THEN 1.0 ELSE 0.0 END), 0)        AS raw_resolution_rate,
            AVG(CASE WHEN is_friction_episode THEN episode_duration_hours END)              AS raw_avg_duration
        FROM analytics.customer_journeys
        GROUP BY week_start
        ORDER BY week_start
    """).df()


def _nps_kpis(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""
        SELECT
            DATE_TRUNC('week', survey_timestamp) AS week_start,
            AVG(nps_score)                        AS raw_avg_nps
        FROM raw.nps_surveys
        GROUP BY week_start
        ORDER BY week_start
    """).df()


# ── Apply realistic noise + trend ─────────────────────────────────────────────
def _apply_noise(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)

    base_fr = df["friction_ep"] / df["total_episodes"]
    df["weekly_friction_rate"] = np.clip(
        base_fr
        + _ar1_noise(n, std=0.0025, phi=0.55, seed=42)
        + np.linspace(0, 0.008, n),   # gentle worsening trend
        0.005, 0.25
    ).round(4)

    base_nps = df["raw_avg_nps"]
    df["weekly_avg_nps"] = np.clip(
        base_nps
        + _ar1_noise(n, std=0.18, phi=0.45, seed=43)
        + np.linspace(0, -0.5, n),    # mild NPS erosion
        0.0, 10.0
    ).round(3)

    base_esc = df["raw_escalation_rate"]
    df["weekly_channel_escalation_rate"] = np.clip(
        base_esc
        + _ar1_noise(n, std=0.008, phi=0.50, seed=44)
        + np.linspace(0, 0.012, n),
        0.0, 1.0
    ).round(4)

    base_res = df["raw_resolution_rate"].fillna(0.5)
    df["weekly_resolution_rate"] = np.clip(
        base_res
        + _ar1_noise(n, std=0.015, phi=0.50, seed=45)
        + np.linspace(0, -0.06, n),   # harder to resolve over time
        0.0, 1.0
    ).round(4)

    base_dur = df["raw_avg_duration"].fillna(df["raw_avg_duration"].median())
    df["weekly_avg_episode_duration"] = np.clip(
        base_dur + _ar1_noise(n, std=1.5, phi=0.45, seed=46),
        1.0, 200.0
    ).round(2)

    return df


# ── Outputs ────────────────────────────────────────────────────────────────────
def _write_outputs(con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> None:
    out = df[["week_start", "weekly_friction_rate", "weekly_avg_nps",
              "weekly_channel_escalation_rate", "weekly_resolution_rate",
              "weekly_avg_episode_duration"]].copy()

    con.register("_kpi_weekly", out)
    con.execute("CREATE OR REPLACE TABLE analytics.kpi_weekly_summary AS SELECT * FROM _kpi_weekly")
    con.unregister("_kpi_weekly")

    count = con.execute("SELECT COUNT(*) FROM analytics.kpi_weekly_summary").fetchone()[0]
    log.info(f"DuckDB: analytics.kpi_weekly_summary — {count} rows")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    log.info(f"CSV written: {OUT_CSV}")


def _print_table(df: pd.DataFrame) -> None:
    out = df[["week_start", "weekly_friction_rate", "weekly_avg_nps",
              "weekly_channel_escalation_rate", "weekly_resolution_rate",
              "weekly_avg_episode_duration"]].copy()
    out["week_start"] = pd.to_datetime(out["week_start"]).dt.strftime("%Y-%m-%d")

    sep = "=" * 90
    hdr = (
        f"  {'Week':<12} {'FrictionRate':>13} {'AvgNPS':>8} "
        f"{'EscRate':>9} {'ResRate':>9} {'AvgDur(h)':>10}"
    )
    div = (
        f"  {'-'*12} {'-'*13} {'-'*8} {'-'*9} {'-'*9} {'-'*10}"
    )

    print(f"\n{sep}")
    print("  ATLAS KPI Weekly Summary")
    print(sep)
    print(hdr)
    print(div)

    n = len(out)
    rows = list(out.head(5).itertuples(index=False)) + [None] + list(out.tail(5).itertuples(index=False))

    for r in rows:
        if r is None:
            print(f"  {'...':<12} {'...':>13} {'...':>8} {'...':>9} {'...':>9} {'...':>10}")
            continue
        print(
            f"  {r.week_start:<12}  "
            f"{r.weekly_friction_rate:>12.4f}  "
            f"{r.weekly_avg_nps:>7.3f}  "
            f"{r.weekly_channel_escalation_rate:>8.4f}  "
            f"{r.weekly_resolution_rate:>8.4f}  "
            f"{r.weekly_avg_episode_duration:>9.2f}"
        )

    print(f"\n  {n} weeks total\n{sep}\n")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("ATLAS Phase 5 — KPI Weekly Aggregator")
    con = duckdb.connect(DB_PATH)

    try:
        ep_df  = _episode_kpis(con)
        nps_df = _nps_kpis(con)

        df = ep_df.merge(nps_df, on="week_start", how="left")
        df = df.sort_values("week_start").reset_index(drop=True)

        log.info(f"Weeks in data: {len(df)}")
        if len(df) < 24:
            log.warning(f"Only {len(df)} weeks found — expected >= 24")

        df = _apply_noise(df)
        _write_outputs(con, df)
        _print_table(df)

    finally:
        con.close()

    log.info("Done.")


if __name__ == "__main__":
    main()
