"""
ATLAS Phase 5 — Friction Scoring Engine
Groups friction episodes by (product_involved, region, dominant_channel),
computes a composite priority_score, and ranks hotspots.
Writes analytics.friction_hotspots + data/processed/friction_hotspots.csv.
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

DB_PATH = os.getenv("DB_PATH", "data/atlas.duckdb")
OUT_CSV = Path("data/processed/friction_hotspots.csv")


# ── Core query ─────────────────────────────────────────────────────────────────
def build_hotspots(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""
        WITH friction_eps AS (
            SELECT
                customer_id,
                product_involved,
                region,
                dominant_channel,
                friction_score,
                eventually_resolved,
                episode_duration_hours
            FROM analytics.customer_journeys
            WHERE is_friction_episode = TRUE
        ),

        -- Average sentiment per customer across all their LLM-analysed events
        li_by_customer AS (
            SELECT customer_id, AVG(sentiment_score) AS avg_sentiment
            FROM analytics.llm_insights
            GROUP BY customer_id
        ),

        -- Most frequent LLM theme per (product, region, channel)
        theme_counts AS (
            SELECT
                fe.product_involved,
                fe.region,
                fe.dominant_channel,
                li.theme,
                COUNT(*) AS cnt
            FROM friction_eps fe
            JOIN analytics.llm_insights li ON fe.customer_id = li.customer_id
            WHERE li.theme IS NOT NULL
            GROUP BY fe.product_involved, fe.region, fe.dominant_channel, li.theme
        ),
        top_themes AS (
            SELECT product_involved, region, dominant_channel, theme AS top_theme
            FROM theme_counts
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY product_involved, region, dominant_channel
                ORDER BY cnt DESC
            ) = 1
        ),

        -- Per-group aggregate stats
        group_stats AS (
            SELECT
                fe.product_involved,
                fe.region,
                fe.dominant_channel,
                COUNT(DISTINCT fe.customer_id)                                    AS affected_customers,
                ROUND(AVG(fe.friction_score), 2)                                  AS avg_friction_score,
                SUM(CASE WHEN NOT fe.eventually_resolved THEN 1 ELSE 0 END)      AS unresolved_count,
                ROUND(
                    CAST(SUM(CASE WHEN NOT fe.eventually_resolved THEN 1 ELSE 0 END) AS DOUBLE)
                    / NULLIF(COUNT(DISTINCT fe.customer_id), 0),
                4)                                                                 AS unresolved_rate,
                ROUND(AVG(lc.avg_sentiment), 4)                                   AS avg_sentiment,
                ROUND(AVG(fe.episode_duration_hours), 2)                          AS avg_episode_duration
            FROM friction_eps fe
            LEFT JOIN li_by_customer lc ON fe.customer_id = lc.customer_id
            GROUP BY fe.product_involved, fe.region, fe.dominant_channel
        )

        SELECT
            gs.product_involved,
            gs.region,
            gs.dominant_channel,
            gs.affected_customers,
            gs.avg_friction_score,
            gs.unresolved_count,
            gs.unresolved_rate,
            gs.avg_sentiment,
            gs.avg_episode_duration,
            tt.top_theme,
            ROUND(
                (gs.avg_friction_score          * 0.35) +
                (LEAST(gs.unresolved_rate, 1.0) * 100 * 0.35) +
                (ABS(COALESCE(gs.avg_sentiment, 0)) * 50 * 0.20) +
                (LEAST(gs.avg_episode_duration / 72.0 * 100, 100) * 0.10),
            2) AS priority_score
        FROM group_stats gs
        LEFT JOIN top_themes tt
            ON  gs.product_involved  = tt.product_involved
            AND gs.region            = tt.region
            AND gs.dominant_channel  = tt.dominant_channel
        ORDER BY priority_score DESC
    """).df()


# ── Outputs ────────────────────────────────────────────────────────────────────
def _write_outputs(con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> None:
    con.register("_hotspots", df)
    con.execute(
        "CREATE OR REPLACE TABLE analytics.friction_hotspots AS SELECT * FROM _hotspots"
    )
    con.unregister("_hotspots")
    count = con.execute("SELECT COUNT(*) FROM analytics.friction_hotspots").fetchone()[0]
    log.info(f"DuckDB: analytics.friction_hotspots — {count} rows")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    log.info(f"CSV written: {OUT_CSV}")


def _print_top10(df: pd.DataFrame) -> None:
    top = df.head(10).reset_index(drop=True)
    sep = "=" * 104

    print(f"\n{sep}")
    print("  ATLAS Friction Hotspots — Top 10")
    print(sep)
    print(
        f"  {'#':>2}  {'Product':<15} {'Region':<12} {'Channel':<10} "
        f"{'Custs':>6} {'AvgScore':>9} {'UnresRate':>10} "
        f"{'AvgSent':>8} {'AvgDur':>8} {'TopTheme':<22} {'Priority':>9}"
    )
    print(
        f"  {'--':>2}  {'-'*15} {'-'*12} {'-'*10} "
        f"{'-'*6} {'-'*9} {'-'*10} "
        f"{'-'*8} {'-'*8} {'-'*22} {'-'*9}"
    )

    for i, r in top.iterrows():
        sent = f"{r['avg_sentiment']:+.3f}" if pd.notna(r["avg_sentiment"]) else "  n/a "
        theme = r["top_theme"] if pd.notna(r["top_theme"]) else "n/a"
        print(
            f"  {i+1:>2}  {r['product_involved']:<15} {r['region']:<12} "
            f"{r['dominant_channel']:<10} {int(r['affected_customers']):>6} "
            f"{r['avg_friction_score']:>9.2f} {r['unresolved_rate']:>10.4f} "
            f"{sent:>8} {r['avg_episode_duration']:>8.2f} "
            f"{theme:<22} {r['priority_score']:>9.2f}"
        )

    print(f"\n  {len(df)} total hotspot segments\n{sep}\n")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("ATLAS Phase 5 — Friction Scoring Engine")
    con = duckdb.connect(DB_PATH)

    try:
        df = build_hotspots(con)
        log.info(f"Hotspot segments computed: {len(df)}")
        _write_outputs(con, df)
        _print_top10(df)
    finally:
        con.close()

    log.info("Done.")


if __name__ == "__main__":
    main()
