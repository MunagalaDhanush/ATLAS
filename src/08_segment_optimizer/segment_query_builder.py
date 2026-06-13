"""
ATLAS Phase 5 — Segment Query Builder
Parameterized query function that dynamically filters customer_journeys
and joins llm_insights to return targeted customer segments.

Usage:
    from segment_query_builder import build_and_run_segment
    df = build_and_run_segment(con, product='credit_card', min_friction_score=50)
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

# Allowed values — validated before interpolating into SQL
_ALLOWED_PRODUCTS = {"checking", "savings", "credit_card", "mortgage", "auto_loan"}
_ALLOWED_REGIONS  = {"Northeast", "Southeast", "Midwest", "West", "Southwest"}
_ALLOWED_CHANNELS = {"call", "branch", "online", "mobile", "survey"}


def _validate(name: str, value: str, allowed: set) -> str:
    if value not in allowed:
        raise ValueError(f"Invalid {name}={value!r}. Allowed: {sorted(allowed)}")
    return value


# ── Public API ─────────────────────────────────────────────────────────────────
def build_and_run_segment(
    con: duckdb.DuckDBPyConnection,
    product:           str | None = None,
    region:            str | None = None,
    min_friction_score: float | None = None,
    channel:           str | None = None,
    date_from:         str | None = None,   # ISO date "YYYY-MM-DD"
    date_to:           str | None = None,
) -> pd.DataFrame:
    """
    Build a filtered segment from friction episodes joined with LLM insights.
    All non-None parameters are ANDed together in the WHERE clause.
    Returns a DataFrame with one row per friction episode.
    """
    conditions: list[str] = ["cj.is_friction_episode = TRUE"]

    if product is not None:
        conditions.append(f"cj.product_involved = '{_validate('product', product, _ALLOWED_PRODUCTS)}'")
    if region is not None:
        conditions.append(f"cj.region = '{_validate('region', region, _ALLOWED_REGIONS)}'")
    if channel is not None:
        conditions.append(f"cj.dominant_channel = '{_validate('channel', channel, _ALLOWED_CHANNELS)}'")
    if min_friction_score is not None:
        conditions.append(f"cj.friction_score >= {float(min_friction_score)}")
    if date_from is not None:
        conditions.append(f"cj.episode_start >= '{date_from}'")
    if date_to is not None:
        conditions.append(f"cj.episode_start <= '{date_to}'")

    where_sql = " AND ".join(conditions)

    query = f"""
        SELECT
            cj.customer_id,
            cj.product_involved,
            cj.region,
            cj.channel_sequence,
            cj.friction_score,
            cj.eventually_resolved,
            cj.episode_duration_hours,
            li.theme,
            li.sentiment_score
        FROM analytics.customer_journeys cj
        LEFT JOIN analytics.llm_insights li
               ON cj.customer_id = li.customer_id
        WHERE {where_sql}
        ORDER BY cj.friction_score DESC
    """
    return con.execute(query).df()


# ── Demo runner ────────────────────────────────────────────────────────────────
def _print_segment(label: str, df: pd.DataFrame) -> None:
    sep = "=" * 80
    print(f"\n{sep}")
    print(f"  Segment: {label}")
    print(f"  {len(df):,} rows matched")
    print(sep)

    if df.empty:
        print("  (no rows)\n")
        return

    sample = df.head(5)
    # Header
    print(
        f"  {'customer_id':<38} {'product':<13} {'region':<11} "
        f"{'score':>6} {'resolved':>9} {'dur(h)':>7} {'theme':<22} {'sent':>6}"
    )
    print(f"  {'-'*38} {'-'*13} {'-'*11} {'-'*6} {'-'*9} {'-'*7} {'-'*22} {'-'*6}")
    for _, r in sample.iterrows():
        theme   = r["theme"] if pd.notna(r["theme"]) else "n/a"
        sent    = f"{r['sentiment_score']:+.2f}" if pd.notna(r["sentiment_score"]) else " n/a"
        print(
            f"  {r['customer_id']:<38} {r['product_involved']:<13} "
            f"{r['region']:<11} {r['friction_score']:>6.1f} "
            f"{'yes' if r['eventually_resolved'] else 'no':>9} "
            f"{r['episode_duration_hours']:>7.1f} {theme:<22} {sent:>6}"
        )

    if len(df) > 5:
        print(f"  ... ({len(df) - 5} more rows)")

    # Quick summary
    print(f"\n  Avg friction score : {df['friction_score'].mean():.2f}")
    print(f"  % unresolved       : {(~df['eventually_resolved']).mean() * 100:.1f}%")
    if df["sentiment_score"].notna().any():
        print(f"  Avg sentiment      : {df['sentiment_score'].mean():+.3f}")
    print()


def main() -> None:
    log.info("ATLAS Phase 5 — Segment Query Builder (demo)")
    con = duckdb.connect(DB_PATH)

    try:
        # Cut 1: credit_card friction with score >= 50
        df1 = build_and_run_segment(con, product="credit_card", min_friction_score=50)
        _print_segment("product=credit_card, min_friction_score=50", df1)

        # Cut 2: Southeast mobile friction
        df2 = build_and_run_segment(con, region="Southeast", channel="mobile")
        _print_segment("region=Southeast, channel=mobile", df2)

        # Cut 3: highest-severity only (score >= 70)
        df3 = build_and_run_segment(con, min_friction_score=70)
        _print_segment("min_friction_score=70 (all regions/products)", df3)

    finally:
        con.close()

    log.info("Done.")


if __name__ == "__main__":
    main()
