"""
ATLAS Phase 3 — Journey Stitcher
Groups customer service events into episodes and scores them for friction.

Episode window: (customer_id, product_involved) events within a 72-hour rolling gap.
A new episode begins when the gap between consecutive events exceeds 72 hours.

Survey events (channel='survey') are excluded — episodes represent service interactions only.

Output:
  - DuckDB: analytics.customer_journeys
  - CSV:    data/processed/customer_journeys.csv
"""

import sys
import logging
from pathlib import Path

import duckdb
import pandas as pd
import numpy as np
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

_ROOT   = Path(__file__).resolve().parents[2]
DB_PATH = str(_ROOT / "data" / "atlas.duckdb")
OUT_CSV = _ROOT / "data" / "processed" / "customer_journeys.csv"
WINDOW_HOURS = 72

# ── Load ───────────────────────────────────────────────────────────────────────
def load_events(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute("""
        SELECT event_id, customer_id, channel, event_timestamp,
               product_involved, issue_category, resolved_flag, region
        FROM   analytics.customer_event_log
        WHERE  channel != 'survey'
    """).df()
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"])
    log.info(f"Loaded {len(df):,} service-channel events from DuckDB")
    return df


# ── Episode windowing (vectorised) ─────────────────────────────────────────────
def assign_episodes(events: pd.DataFrame) -> pd.DataFrame:
    df = (
        events
        .sort_values(["customer_id", "product_involved", "event_timestamp"])
        .copy()
    )

    grp = df.groupby(["customer_id", "product_involved"], sort=False)

    # Time gap to the previous event within each (customer_id, product_involved)
    df["_prev_ts"]    = grp["event_timestamp"].shift(1)
    df["_gap_hours"]  = (df["event_timestamp"] - df["_prev_ts"]).dt.total_seconds() / 3600

    # Boundary = first event of group (NaN gap) OR gap > 72 h
    df["_boundary"]   = df["_gap_hours"].isna() | (df["_gap_hours"] > WINDOW_HOURS)

    # Cumulative boundary count within group = episode sequence number (1-based)
    df["_ep_num"]     = grp["_boundary"].cumsum()

    # Unique episode key: customer + product + episode_num
    df["episode_id"]  = (
        df["customer_id"] + "||"
        + df["product_involved"] + "||"
        + df["_ep_num"].astype(int).astype(str)
    )

    df.drop(columns=["_prev_ts", "_gap_hours", "_boundary", "_ep_num"], inplace=True)
    log.info(f"Assigned {df['episode_id'].nunique():,} unique episodes")
    return df


# ── Episode aggregation ────────────────────────────────────────────────────────
def _channel_seq(chans: pd.Series) -> str:
    """Deduplicated channel names in time order."""
    seen: list[str] = []
    for ch in chans:
        if ch not in seen:
            seen.append(ch)
    return " > ".join(seen)


def build_episodes(events: pd.DataFrame) -> pd.DataFrame:
    # Pre-sort so channel_sequence and time-order aggregations are correct
    ev = events.sort_values(["episode_id", "event_timestamp"])

    # Core aggregations
    agg = ev.groupby("episode_id").agg(
        customer_id      =("customer_id",    "first"),
        product_involved =("product_involved","first"),
        region           =("region",         "first"),
        episode_start    =("event_timestamp", "min"),
        episode_end      =("event_timestamp", "max"),
        distinct_channels=("channel",        "nunique"),
        total_contacts   =("event_timestamp", "count"),
        eventually_resolved=("resolved_flag","any"),
    )

    agg["episode_duration_hours"] = (
        (agg["episode_end"] - agg["episode_start"]).dt.total_seconds() / 3600
    )

    # Channel sequence (deduplicated, time-ordered)
    agg["channel_sequence"] = (
        ev.groupby("episode_id")["channel"]
        .apply(_channel_seq)
    )

    # Issue categories (sorted, unique, comma-joined)
    agg["issue_categories"] = (
        ev.groupby("episode_id")["issue_category"]
        .apply(lambda s: ",".join(sorted(set(s.dropna()))))
    )

    # Dominant channel (most events; tie-break by first appearance)
    dom = (
        ev.groupby(["episode_id", "channel"])
        .size()
        .reset_index(name="cnt")
        .sort_values(["episode_id", "cnt", "channel"], ascending=[True, False, True])
        .groupby("episode_id")["channel"]
        .first()
    )
    agg["dominant_channel"] = dom

    log.info(f"Built {len(agg):,} episodes")
    return agg.reset_index()


# ── Friction rules ─────────────────────────────────────────────────────────────
def apply_friction_rules(episodes: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    ep = episodes.copy()

    # Rule3 helper: same issue_category appearing in 2+ distinct channels within episode
    issue_channel_counts = (
        events.groupby(["episode_id", "issue_category"])["channel"]
        .nunique()
    )
    rule3_flag = (
        issue_channel_counts[issue_channel_counts >= 2]
        .groupby("episode_id")
        .any()
        .reindex(ep["episode_id"], fill_value=False)
        .values
    )

    multi     = ep["distinct_channels"] >= 2
    unresolved= ~ep["eventually_resolved"]
    long_ep   = ep["episode_duration_hours"] > 48
    heavy     = ep["total_contacts"] >= 3

    ep["rule1"] = multi & unresolved
    ep["rule2"] = heavy
    ep["rule3"] = pd.Series(rule3_flag, index=ep.index)
    ep["rule4"] = multi & ep["eventually_resolved"] & long_ep

    ep["is_friction_episode"] = ep[["rule1", "rule2", "rule3", "rule4"]].any(axis=1)

    def _rules_triggered(row):
        triggered = [f"Rule{i}" for i, r in enumerate([row.rule1, row.rule2, row.rule3, row.rule4], 1) if r]
        return ",".join(triggered)

    ep["rules_triggered"] = ep.apply(_rules_triggered, axis=1)

    n_fric = ep["is_friction_episode"].sum()
    log.info(
        f"Friction rules applied: {n_fric:,} friction episodes "
        f"({n_fric / len(ep):.1%} of {len(ep):,} total)"
    )
    return ep.drop(columns=["rule1", "rule2", "rule3", "rule4"])


# ── Friction score ─────────────────────────────────────────────────────────────
def calc_friction_score(episodes: pd.DataFrame) -> pd.DataFrame:
    ep = episodes.copy()
    ep["friction_score"] = (
        ep["distinct_channels"].clip(upper=40 // 15 + 1).mul(15).clip(upper=40)
        + ep["total_contacts"].mul(8).clip(upper=30)
        + (~ep["eventually_resolved"]).astype(int) * 20
        + (ep["episode_duration_hours"] > 24).astype(int) * 10
    ).clip(upper=100).astype(float)
    return ep


# ── Write outputs ──────────────────────────────────────────────────────────────
def write_outputs(con: duckdb.DuckDBPyConnection, episodes: pd.DataFrame) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    episodes.to_csv(OUT_CSV, index=False)
    log.info(f"CSV written: {OUT_CSV}")

    con.register("_episodes", episodes)
    con.execute("CREATE OR REPLACE TABLE analytics.customer_journeys AS SELECT * FROM _episodes")
    con.unregister("_episodes")
    count = con.execute("SELECT COUNT(*) FROM analytics.customer_journeys").fetchone()[0]
    log.info(f"DuckDB: analytics.customer_journeys — {count:,} rows")


# ── Summary ────────────────────────────────────────────────────────────────────
def print_summary(episodes: pd.DataFrame) -> None:
    total   = len(episodes)
    fric    = episodes["is_friction_episode"].sum()
    rate    = fric / total * 100

    print("\n=== Journey Stitcher Summary ===")
    print(f"  Total episodes:     {total:>8,}")
    print(f"  Friction episodes:  {fric:>8,}  ({rate:.1f}%)")

    print("\n  Top 5 products by friction volume:")
    top_prod = (
        episodes[episodes["is_friction_episode"]]
        .groupby("product_involved")
        .size()
        .sort_values(ascending=False)
        .head(5)
    )
    for prod, n in top_prod.items():
        total_prod = (episodes["product_involved"] == prod).sum()
        print(f"    {prod:<15}  {n:>5,} friction  /  {total_prod:>6,} total  ({n/total_prod*100:.1f}%)")

    print("\n  Top 3 friction channel sequences:")
    top_seq = (
        episodes[episodes["is_friction_episode"]]
        .groupby("channel_sequence")
        .size()
        .sort_values(ascending=False)
        .head(3)
    )
    for seq, n in top_seq.items():
        print(f"    {seq:<30}  {n:>5,} episodes")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("ATLAS Phase 3 — Journey Stitcher")
    con = duckdb.connect(DB_PATH)

    try:
        events   = load_events(con)
        events   = assign_episodes(events)
        episodes = build_episodes(events)
        episodes = apply_friction_rules(episodes, events)
        episodes = calc_friction_score(episodes)
        write_outputs(con, episodes)
        print_summary(episodes)
    finally:
        con.close()

    log.info("Done.")


if __name__ == "__main__":
    main()
