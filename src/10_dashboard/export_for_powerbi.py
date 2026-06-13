"""
ATLAS Phase 6 — Power BI Data Exporter
Pulls all dashboard-ready tables from DuckDB, renames columns to Power BI
friendly labels (no underscores, title case), and exports to data/dashboard/.
"""

import os
import logging
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DB_PATH   = os.getenv("DB_PATH", "data/atlas.duckdb")
DASH_DIR  = Path("data/dashboard")


# ── Individual exporters ───────────────────────────────────────────────────────

def _export_friction_hotspots(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute("SELECT * FROM analytics.friction_hotspots ORDER BY priority_score DESC").df()
    return df.rename(columns={
        "product_involved":   "Product",
        "region":             "Region",
        "dominant_channel":   "Channel",
        "affected_customers": "Customers",
        "avg_friction_score": "Friction Score",
        "unresolved_count":   "Unresolved Count",
        "unresolved_rate":    "Unresolved Rate",
        "avg_sentiment":      "Avg Sentiment",
        "avg_episode_duration": "Avg Duration Hours",
        "top_theme":          "Top Theme",
        "priority_score":     "Priority Score",
    })


def _export_kpi_trend(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute("SELECT * FROM analytics.kpi_weekly_summary ORDER BY week_start").df()
    return df.rename(columns={
        "week_start":                      "Week",
        "weekly_friction_rate":            "Friction Rate",
        "weekly_avg_nps":                  "NPS Score",
        "weekly_channel_escalation_rate":  "Escalation Rate",
        "weekly_resolution_rate":          "Resolution Rate",
        "weekly_avg_episode_duration":     "Avg Episode Duration",
    })


def _export_kpi_alerts(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute("SELECT * FROM analytics.kpi_alerts ORDER BY kpi_name").df()
    return df.rename(columns={
        "kpi_name":       "KPI",
        "current_value":  "Current Value",
        "forecast_value": "Forecast Value",
        "pct_change":     "Change Pct",
        "is_stationary":  "Is Stationary",
        "alert_fired":    "Alert Fired",
        "direction":      "Direction",
        "adf_pvalue":     "ADF P-Value",
    })


def _export_llm_theme_summary(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute("SELECT * FROM analytics.llm_theme_summary ORDER BY count DESC").df()
    return df.rename(columns={
        "theme":            "Theme",
        "count":            "Count",
        "avg_sentiment":    "Avg Sentiment",
        "pct_unresolved":   "Pct Unresolved",
        "avg_urgency_score": "Avg Urgency Score",
    })


def _export_customer_journeys(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute("""
        SELECT
            customer_id,
            product_involved,
            region,
            channel_sequence,
            friction_score,
            is_friction_episode,
            eventually_resolved,
            episode_duration_hours,
            distinct_channels,
            total_contacts
        FROM analytics.customer_journeys
        ORDER BY friction_score DESC
    """).df()
    return df.rename(columns={
        "product_involved":     "Product",
        "channel_sequence":     "Channel Sequence",
        "friction_score":       "Friction Score",
        "is_friction_episode":  "Is Friction",
        "eventually_resolved":  "Resolved",
        "episode_duration_hours": "Duration Hours",
        "distinct_channels":    "Channels Used",
        "total_contacts":       "Total Contacts",
    })


def _export_segment_cuts(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    base_sql = """
        SELECT
            cj.customer_id,
            cj.product_involved  AS Product,
            cj.region            AS Region,
            cj.channel_sequence  AS "Channel Sequence",
            cj.friction_score    AS "Friction Score",
            cj.eventually_resolved AS Resolved,
            cj.episode_duration_hours AS "Duration Hours",
            li.theme             AS Theme,
            li.sentiment_score   AS "Sentiment Score"
        FROM analytics.customer_journeys cj
        LEFT JOIN analytics.llm_insights li ON cj.customer_id = li.customer_id
        WHERE cj.is_friction_episode = TRUE
    """

    cuts = [
        ("Credit Card High Friction",
         base_sql + " AND cj.product_involved = 'credit_card' AND cj.friction_score >= 50"),
        ("Southeast Mobile",
         base_sql + " AND cj.region = 'Southeast' AND cj.dominant_channel = 'mobile'"),
        ("Critical Severity",
         base_sql + " AND cj.friction_score >= 70"),
    ]

    frames = []
    for label, sql in cuts:
        df = con.execute(sql + " ORDER BY cj.friction_score DESC").df()
        df.insert(0, "Segment Label", label)
        frames.append(df)

    return pd.concat(frames, ignore_index=True)


# ── Writer + summary ───────────────────────────────────────────────────────────

def _save(df: pd.DataFrame, filename: str) -> None:
    path = DASH_DIR / filename
    df.to_csv(path, index=False)
    size_kb = path.stat().st_size / 1024
    log.info(f"  {filename:<35} {len(df):>6} rows  {size_kb:>7.1f} KB")


def _print_summary(results: list[tuple[str, int, float]]) -> None:
    sep = "=" * 66
    print(f"\n{sep}")
    print("  ATLAS Power BI Export — File Summary")
    print(sep)
    print(f"  {'File':<35} {'Rows':>6}  {'Size (KB)':>10}")
    print(f"  {'-'*35} {'-'*6}  {'-'*10}")
    total_rows = 0
    for name, rows, size_kb in results:
        print(f"  {name:<35} {rows:>6}  {size_kb:>10.1f}")
        total_rows += rows
    print(f"  {'-'*35} {'-'*6}  {'-'*10}")
    print(f"  {'TOTAL':<35} {total_rows:>6}")
    print(f"\n  Destination: {DASH_DIR.resolve()}\n{sep}\n")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("ATLAS Phase 6 — Power BI Data Exporter")
    DASH_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(DB_PATH)
    results: list[tuple[str, int, float]] = []

    try:
        exports = [
            ("Friction Hotspots.csv",    _export_friction_hotspots),
            ("KPI Weekly Trend.csv",     _export_kpi_trend),
            ("KPI Alerts.csv",           _export_kpi_alerts),
            ("LLM Theme Summary.csv",    _export_llm_theme_summary),
            ("Customer Journeys.csv",    _export_customer_journeys),
            ("Segment Cuts.csv",         _export_segment_cuts),
        ]

        log.info("Exporting tables:")
        for filename, fn in exports:
            df = fn(con)
            _save(df, filename)
            size_kb = (DASH_DIR / filename).stat().st_size / 1024
            results.append((filename, len(df), size_kb))

    finally:
        con.close()

    _print_summary(results)
    log.info("Done.")


if __name__ == "__main__":
    main()
