"""
ATLAS Phase 4 — Theme Extractor
Samples 500 text-bearing events from DuckDB, calls Groq for each,
and writes structured results to analytics.llm_insights.

Rate-limit strategy: process in batches of 25, sleep 2s between batches.
Exponential backoff inside extract_insight() handles mid-batch 429s.

Output:
  - DuckDB: analytics.llm_insights
  - CSV:    data/processed/llm_insights.csv
"""

import os
import sys
import time
import logging
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from groq_client import extract_insight

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DB_PATH    = os.getenv("DB_PATH", "data/atlas.duckdb")
OUT_CSV    = Path("data/processed/llm_insights.csv")
SAMPLE_N   = 500
BATCH_SIZE = 25


# ── Schema setup ───────────────────────────────────────────────────────────────
def _ensure_table(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS analytics.llm_insights (
            event_id        VARCHAR,
            customer_id     VARCHAR,
            channel         VARCHAR,
            theme           VARCHAR,
            sentiment_score DOUBLE,
            unresolved_issue BOOLEAN,
            urgency_level   VARCHAR,
            key_phrase      VARCHAR,
            processed_at    TIMESTAMP
        )
    """)


# ── Load candidates ────────────────────────────────────────────────────────────
def load_candidates(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute("""
        SELECT event_id, customer_id, channel, text_content
        FROM   analytics.customer_event_log
        WHERE  text_content IS NOT NULL
          AND  LENGTH(text_content) > 15
    """).df()
    log.info(f"Text-bearing events: {len(df):,}")
    return df


# ── Processing loop ────────────────────────────────────────────────────────────
def run_extraction(candidates: pd.DataFrame) -> pd.DataFrame:
    sample = candidates.sample(n=min(SAMPLE_N, len(candidates)), random_state=42)
    log.info(f"Sampled {len(sample):,} rows for extraction")

    total_batches = (len(sample) + BATCH_SIZE - 1) // BATCH_SIZE
    rows: list[dict] = []
    n_ok = n_fail = 0

    for batch_idx in range(total_batches):
        start = batch_idx * BATCH_SIZE
        batch = sample.iloc[start : start + BATCH_SIZE]

        for _, row in batch.iterrows():
            insight = extract_insight(row["text_content"], event_id=row["event_id"])
            if insight:
                rows.append({
                    "event_id":        row["event_id"],
                    "customer_id":     row["customer_id"],
                    "channel":         row["channel"],
                    "theme":           insight["theme"],
                    "sentiment_score": insight["sentiment_score"],
                    "unresolved_issue": insight["unresolved_issue"],
                    "urgency_level":   insight["urgency_level"],
                    "key_phrase":      insight["key_phrase"],
                    "processed_at":    pd.Timestamp.now(),
                })
                n_ok += 1
            else:
                n_fail += 1

        processed = min(start + BATCH_SIZE, len(sample))

        # Progress every 5 batches
        if (batch_idx + 1) % 5 == 0 or (batch_idx + 1) == total_batches:
            log.info(
                f"Processed {processed}/{len(sample)}  "
                f"(ok={n_ok}, failed={n_fail})"
            )

        # Rate-limit buffer between batches (not after the last one)
        if batch_idx < total_batches - 1:
            time.sleep(2)

    log.info(f"Extraction complete — {n_ok} succeeded, {n_fail} failed")
    return pd.DataFrame(rows)


# ── Write outputs ──────────────────────────────────────────────────────────────
def write_outputs(con: duckdb.DuckDBPyConnection, results: pd.DataFrame) -> None:
    # Overwrite table with fresh results for this run
    con.register("_insights", results)
    con.execute("CREATE OR REPLACE TABLE analytics.llm_insights AS SELECT * FROM _insights")
    con.unregister("_insights")

    count = con.execute("SELECT COUNT(*) FROM analytics.llm_insights").fetchone()[0]
    log.info(f"DuckDB: analytics.llm_insights — {count:,} rows")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(OUT_CSV, index=False)
    log.info(f"CSV written: {OUT_CSV}")


# ── Summary ────────────────────────────────────────────────────────────────────
def print_summary(results: pd.DataFrame) -> None:
    print(f"\n=== Theme Extractor — Final Summary ===")
    print(f"  Rows written:  {len(results):,}")
    print(f"  Channels:      {results['channel'].value_counts().to_dict()}")
    print(f"\n  Theme distribution:")
    theme_counts = results["theme"].value_counts()
    for theme, cnt in theme_counts.items():
        pct = cnt / len(results) * 100
        print(f"    {theme:<25}  {cnt:>4}  ({pct:.1f}%)")
    print(f"\n  Avg sentiment overall:  {results['sentiment_score'].mean():.3f}")
    print(f"  Pct unresolved issues:  {results['unresolved_issue'].mean() * 100:.1f}%")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("ATLAS Phase 4 — Theme Extractor")
    con = duckdb.connect(DB_PATH)

    try:
        _ensure_table(con)
        candidates = load_candidates(con)
        results    = run_extraction(candidates)

        if results.empty:
            log.error("No results — check GROQ_API_KEY and connectivity.")
            return

        write_outputs(con, results)
        print_summary(results)

    finally:
        con.close()

    log.info("Done.")


if __name__ == "__main__":
    main()
