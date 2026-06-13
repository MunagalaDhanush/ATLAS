"""
ATLAS Phase 3 — Friction Detector
Statistical analysis of friction patterns from CUSTOMER_JOURNEYS.

Outputs:
  - data/processed/friction_flags.csv
  - DuckDB: analytics.friction_flags

Prints:
  - Overall friction rate
  - Chi-square test (friction distribution across products)
  - Top 3 friction-prone products, regions, channel sequences
"""

import logging
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

_ROOT   = Path(__file__).resolve().parents[2]
DB_PATH = str(_ROOT / "data" / "atlas.duckdb")
IN_CSV  = _ROOT / "data" / "processed" / "customer_journeys.csv"
OUT_CSV = _ROOT / "data" / "processed" / "friction_flags.csv"


# ── Load ───────────────────────────────────────────────────────────────────────
def load_journeys() -> pd.DataFrame:
    if not IN_CSV.exists():
        raise FileNotFoundError(f"{IN_CSV} not found — run journey_stitcher.py first")
    df = pd.read_csv(IN_CSV, parse_dates=["episode_start", "episode_end"])
    log.info(f"Loaded {len(df):,} episodes from {IN_CSV.name}")
    return df


def load_region_map(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """One region per customer — kept for future joins; journeys CSV already includes region."""
    return con.execute("""
        SELECT DISTINCT customer_id, region
        FROM analytics.customer_event_log
    """).df()


# ── Chi-square test ────────────────────────────────────────────────────────────
def chi_square_by_product(journeys: pd.DataFrame) -> tuple[float, float, pd.Series]:
    """Test whether friction episodes are uniformly distributed across products."""
    observed = (
        journeys[journeys["is_friction_episode"]]
        .groupby("product_involved")
        .size()
        .sort_index()
    )
    expected_uniform = np.full(len(observed), observed.sum() / len(observed))
    chi2, p = stats.chisquare(f_obs=observed.values, f_exp=expected_uniform)
    return chi2, p, observed


# ── Rate tables ────────────────────────────────────────────────────────────────
def friction_rate_by_product(journeys: pd.DataFrame) -> pd.DataFrame:
    grp = journeys.groupby("product_involved").agg(
        total=("is_friction_episode", "count"),
        friction=("is_friction_episode", "sum"),
    )
    grp["rate_pct"] = grp["friction"] / grp["total"] * 100
    return grp.sort_values("rate_pct", ascending=False)


def friction_rate_by_region(journeys: pd.DataFrame) -> pd.DataFrame:
    grp = journeys.groupby("region").agg(
        total=("is_friction_episode", "count"),
        friction=("is_friction_episode", "sum"),
    )
    grp["rate_pct"] = grp["friction"] / grp["total"] * 100
    return grp.sort_values("rate_pct", ascending=False)


def friction_rate_by_sequence(journeys: pd.DataFrame) -> pd.DataFrame:
    grp = journeys.groupby("channel_sequence").agg(
        total=("is_friction_episode", "count"),
        friction=("is_friction_episode", "sum"),
    )
    grp["rate_pct"] = grp["friction"] / grp["total"] * 100
    return grp.sort_values("friction", ascending=False)


# ── Build friction_flags ───────────────────────────────────────────────────────
def build_friction_flags(journeys: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "customer_id", "product_involved",
        "episode_start", "episode_end",
        "friction_score", "is_friction_episode",
        "rules_triggered", "dominant_channel",
    ]
    flags = journeys[cols].copy()
    flags = flags[flags["is_friction_episode"]].reset_index(drop=True)
    log.info(f"Friction flags: {len(flags):,} friction episodes")
    return flags


# ── Write outputs ──────────────────────────────────────────────────────────────
def write_outputs(
    con: duckdb.DuckDBPyConnection,
    flags: pd.DataFrame,
    journeys: pd.DataFrame,
) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    flags.to_csv(OUT_CSV, index=False)
    log.info(f"CSV written: {OUT_CSV}")

    # Write full flags (all episodes, not just friction) so analysts can filter
    con.register("_flags", journeys[[
        "customer_id", "product_involved", "episode_start", "episode_end",
        "friction_score", "is_friction_episode", "rules_triggered", "dominant_channel",
    ]])
    con.execute("CREATE OR REPLACE TABLE analytics.friction_flags AS SELECT * FROM _flags")
    con.unregister("_flags")
    count = con.execute("SELECT COUNT(*) FROM analytics.friction_flags").fetchone()[0]
    log.info(f"DuckDB: analytics.friction_flags — {count:,} rows")


# ── Print summary ──────────────────────────────────────────────────────────────
def print_summary(
    journeys:    pd.DataFrame,
    chi2:        float,
    p_val:       float,
    by_product:  pd.DataFrame,
    by_region:   pd.DataFrame,
    by_sequence: pd.DataFrame,
) -> None:
    total  = len(journeys)
    fric   = journeys["is_friction_episode"].sum()
    rate   = fric / total * 100

    print("\n=== Friction Detector Results ===")
    print(f"  Overall friction rate:  {rate:.1f}%  ({fric:,} / {total:,} episodes)")

    print(f"\n  Chi-square test (friction distribution across products):")
    print(f"    Statistic:  {chi2:.4f}")
    print(f"    p-value:    {p_val:.6f}")
    sig = "significant (products differ in friction rate)" if p_val < 0.05 else "not significant"
    print(f"    Result:     {sig}  (alpha=0.05)")

    print("\n  Top 3 friction-prone products:")
    for prod, row in by_product.head(3).iterrows():
        print(f"    {prod:<15}  {row['rate_pct']:5.1f}%  ({int(row['friction']):,} friction / {int(row['total']):,} total)")

    print("\n  Top 3 friction-prone regions:")
    for region, row in by_region.head(3).iterrows():
        print(f"    {region:<12}  {row['rate_pct']:5.1f}%  ({int(row['friction']):,} / {int(row['total']):,})")

    print("\n  Top 3 friction channel sequences:")
    for seq, row in by_sequence.head(3).iterrows():
        print(f"    {seq:<35}  {int(row['friction']):,} episodes  ({row['rate_pct']:.1f}% friction rate)")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("ATLAS Phase 3 — Friction Detector")
    con = duckdb.connect(DB_PATH)

    try:
        journeys   = load_journeys()

        chi2, p_val, _obs = chi_square_by_product(journeys)

        by_product  = friction_rate_by_product(journeys)
        by_region   = friction_rate_by_region(journeys)
        by_sequence = friction_rate_by_sequence(journeys)

        flags = build_friction_flags(journeys)
        write_outputs(con, flags, journeys)

        print_summary(journeys, chi2, p_val, by_product, by_region, by_sequence)

    finally:
        con.close()

    log.info("Done.")


if __name__ == "__main__":
    main()
