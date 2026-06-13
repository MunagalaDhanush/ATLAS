"""
ATLAS Phase 4 — Insight Aggregator
Runs analytics on analytics.llm_insights and produces a theme-level summary.

Aggregations:
  - Theme frequency + avg sentiment + % unresolved + avg urgency score
  - Avg sentiment per channel
  - Urgency level distribution
  - Top 10 key phrases by frequency
  - Friction vs non-friction avg sentiment comparison

Output:
  - DuckDB: analytics.llm_theme_summary
  - CSV:    data/processed/llm_theme_summary.csv
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
OUT_CSV = Path("data/processed/llm_theme_summary.csv")


# ── Aggregation queries ────────────────────────────────────────────────────────
def theme_summary(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""
        SELECT
            theme,
            COUNT(*)                                             AS count,
            ROUND(AVG(sentiment_score), 3)                       AS avg_sentiment,
            ROUND(AVG(CASE WHEN unresolved_issue THEN 1.0
                           ELSE 0.0 END) * 100.0, 1)            AS pct_unresolved,
            ROUND(AVG(CASE urgency_level
                          WHEN 'low'      THEN 1.0
                          WHEN 'medium'   THEN 2.0
                          WHEN 'high'     THEN 3.0
                          WHEN 'critical' THEN 4.0
                          ELSE 2.0 END), 2)                      AS avg_urgency_score
        FROM analytics.llm_insights
        GROUP BY theme
        ORDER BY count DESC
    """).df()


def channel_sentiment(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""
        SELECT
            channel,
            COUNT(*)                                             AS n_events,
            ROUND(AVG(sentiment_score), 3)                       AS avg_sentiment,
            ROUND(AVG(CASE WHEN unresolved_issue THEN 1.0
                           ELSE 0.0 END) * 100.0, 1)            AS pct_unresolved
        FROM analytics.llm_insights
        GROUP BY channel
        ORDER BY avg_sentiment
    """).df()


def urgency_distribution(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""
        SELECT
            urgency_level,
            COUNT(*) AS count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM analytics.llm_insights
        GROUP BY urgency_level
        ORDER BY CASE urgency_level
            WHEN 'low' THEN 1 WHEN 'medium' THEN 2
            WHEN 'high' THEN 3 WHEN 'critical' THEN 4 END
    """).df()


def top_key_phrases(con: duckdb.DuckDBPyConnection, n: int = 10) -> pd.DataFrame:
    return con.execute(f"""
        SELECT key_phrase, COUNT(*) AS freq
        FROM analytics.llm_insights
        WHERE key_phrase IS NOT NULL AND key_phrase != ''
        GROUP BY key_phrase
        ORDER BY freq DESC, key_phrase
        LIMIT {n}
    """).df()


def friction_vs_nonfiction(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""
        WITH friction_custs AS (
            SELECT DISTINCT customer_id
            FROM   analytics.friction_flags
            WHERE  is_friction_episode = TRUE
        )
        SELECT
            CASE WHEN fc.customer_id IS NOT NULL
                 THEN 'friction' ELSE 'non_friction' END  AS customer_type,
            COUNT(*)                                       AS event_count,
            ROUND(AVG(li.sentiment_score), 3)              AS avg_sentiment,
            ROUND(AVG(CASE WHEN li.unresolved_issue
                           THEN 1.0 ELSE 0.0 END) * 100.0, 1) AS pct_unresolved
        FROM analytics.llm_insights li
        LEFT JOIN friction_custs fc ON li.customer_id = fc.customer_id
        GROUP BY customer_type
        ORDER BY customer_type
    """).df()


# ── Write outputs ──────────────────────────────────────────────────────────────
def write_outputs(con: duckdb.DuckDBPyConnection, summary_df: pd.DataFrame) -> None:
    con.register("_summary", summary_df)
    con.execute("""
        CREATE OR REPLACE TABLE analytics.llm_theme_summary AS
        SELECT * FROM _summary
    """)
    con.unregister("_summary")
    count = con.execute("SELECT COUNT(*) FROM analytics.llm_theme_summary").fetchone()[0]
    log.info(f"DuckDB: analytics.llm_theme_summary — {count} rows")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(OUT_CSV, index=False)
    log.info(f"CSV written: {OUT_CSV}")


# ── Print summary ──────────────────────────────────────────────────────────────
def print_summary(
    themes:     pd.DataFrame,
    channels:   pd.DataFrame,
    urgency:    pd.DataFrame,
    phrases:    pd.DataFrame,
    fric_comp:  pd.DataFrame,
) -> None:
    sep = "=" * 66

    print(f"\n{sep}")
    print("  ATLAS LLM Insight Aggregator — Results")
    print(sep)

    # ── Theme frequency ────────────────────────────────────────────────────────
    total_events = themes["count"].sum()
    print(f"\n  Theme frequency  (n={total_events:,} events analysed):")
    print(f"  {'Theme':<25} {'N':>5}  {'AvgSent':>8}  {'%Unres':>7}  {'AvgUrg':>7}")
    print(f"  {'-'*25} {'-'*5}  {'-'*8}  {'-'*7}  {'-'*7}")
    for _, r in themes.iterrows():
        print(
            f"  {r['theme']:<25} {int(r['count']):>5}  "
            f"{r['avg_sentiment']:>+8.3f}  "
            f"{r['pct_unresolved']:>6.1f}%  "
            f"{r['avg_urgency_score']:>7.2f}"
        )

    # ── Channel sentiment ──────────────────────────────────────────────────────
    print(f"\n  Avg sentiment by channel:")
    print(f"  {'Channel':<10} {'N':>6}  {'AvgSent':>8}  {'%Unres':>7}")
    print(f"  {'-'*10} {'-'*6}  {'-'*8}  {'-'*7}")
    for _, r in channels.iterrows():
        print(
            f"  {r['channel']:<10} {int(r['n_events']):>6}  "
            f"{r['avg_sentiment']:>+8.3f}  "
            f"{r['pct_unresolved']:>6.1f}%"
        )

    # ── Urgency distribution ───────────────────────────────────────────────────
    print(f"\n  Urgency level distribution:")
    for _, r in urgency.iterrows():
        bar = "#" * int(r["pct"] / 2)
        print(f"  {r['urgency_level']:<10} {int(r['count']):>5}  ({r['pct']:>5.1f}%)  {bar}")

    # ── Top key phrases ────────────────────────────────────────────────────────
    print(f"\n  Top {len(phrases)} key phrases by frequency:")
    for _, r in phrases.iterrows():
        print(f"  {int(r['freq']):>3}x  {r['key_phrase']}")

    # ── Friction vs non-friction ───────────────────────────────────────────────
    print(f"\n  Friction vs non-friction sentiment comparison:")
    print(f"  {'Customer type':<15} {'N events':>9}  {'AvgSent':>8}  {'%Unres':>7}")
    print(f"  {'-'*15} {'-'*9}  {'-'*8}  {'-'*7}")
    for _, r in fric_comp.iterrows():
        print(
            f"  {r['customer_type']:<15} {int(r['event_count']):>9}  "
            f"{r['avg_sentiment']:>+8.3f}  "
            f"{r['pct_unresolved']:>6.1f}%"
        )

    if len(fric_comp) == 2:
        delta = fric_comp.set_index("customer_type")["avg_sentiment"]
        diff = delta.get("friction", 0) - delta.get("non_friction", 0)
        direction = "lower" if diff < 0 else "higher"
        print(f"\n  Friction customers sentiment is {abs(diff):.3f} pts {direction} than non-friction.")

    print(f"\n{sep}\n")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("ATLAS Phase 4 — Insight Aggregator")
    con = duckdb.connect(DB_PATH)

    try:
        # Guard: llm_insights must exist and be populated
        count = con.execute(
            "SELECT COUNT(*) FROM analytics.llm_insights"
        ).fetchone()[0]
        if count == 0:
            log.error("analytics.llm_insights is empty — run theme_extractor.py first.")
            return
        log.info(f"analytics.llm_insights: {count:,} rows")

        themes    = theme_summary(con)
        channels  = channel_sentiment(con)
        urgency   = urgency_distribution(con)
        phrases   = top_key_phrases(con)
        fric_comp = friction_vs_nonfiction(con)

        write_outputs(con, themes)
        print_summary(themes, channels, urgency, phrases, fric_comp)

    finally:
        con.close()

    log.info("Done.")


if __name__ == "__main__":
    main()
