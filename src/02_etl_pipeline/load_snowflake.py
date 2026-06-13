"""
ATLAS ETL — Stage 3: Load to Snowflake
Truncate-and-reload pattern:
  1. Load each source CSV into ATLAS_DB.RAW.<TABLE>
  2. Load unified DataFrame into ATLAS_DB.ANALYTICS.CUSTOMER_EVENT_LOG
  3. Print verification stats (row counts, friction count, null check, sample rows)

Run directly to execute the full pipeline manually:
  python load_snowflake.py
"""

import os
import sys
import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest import ingest
from clean_normalize import normalize

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

_DB  = lambda: os.getenv("SNOWFLAKE_DATABASE", "ATLAS_DB")
_RAW = "RAW"
_ANA = "ANALYTICS"

# Column rename needed for RAW.CALL_CENTER_LOGS (CSV uses call_duration_seconds, DDL uses call_duration_sec)
RAW_TABLE_MAP: dict[str, tuple[str, dict]] = {
    "call_center_logs": ("CALL_CENTER_LOGS", {"call_duration_seconds": "call_duration_sec"}),
    "branch_visits":    ("BRANCH_VISITS",    {}),
    "online_events":    ("ONLINE_EVENTS",    {}),
    "mobile_events":    ("MOBILE_EVENTS",    {}),
    "nps_surveys":      ("NPS_SURVEYS",      {}),
}


# ── Connection ─────────────────────────────────────────────────────────────────
def _connect():
    try:
        import snowflake.connector
    except ImportError:
        raise ImportError("snowflake-connector-python not installed. Run: pip install snowflake-connector-python")

    required = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD",
                "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise EnvironmentError(
            f"Missing .env keys: {missing}\n"
            "Fill in your .env file before running the load."
        )

    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=_RAW,
        session_parameters={"TIMEZONE": "UTC"},
    )


# ── Core load helper ───────────────────────────────────────────────────────────
def _truncate_and_load(conn, df: pd.DataFrame, schema: str, table: str) -> int:
    from snowflake.connector.pandas_tools import write_pandas

    full = f"{_DB()}.{schema}.{table}"

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {full}")
        before = cur.fetchone()[0]

    log.info(f"[{full}] pre-load count: {before:,}  — truncating...")
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE IF EXISTS {full}")

    # Uppercase column names: Snowflake stores unquoted identifiers as UPPERCASE
    df_load = df.copy()
    df_load.columns = [c.upper() for c in df_load.columns]

    success, nchunks, nrows, _ = write_pandas(
        conn, df_load, table,
        database=_DB(), schema=schema,
        quote_identifiers=False,
        chunk_size=16_000,
    )

    if not success:
        raise RuntimeError(f"write_pandas reported failure for {full}")

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {full}")
        after = cur.fetchone()[0]

    log.info(f"[{full}] loaded {nrows:,} rows across {nchunks} chunk(s) — post-load count: {after:,}")
    return after


# ── Public API ─────────────────────────────────────────────────────────────────
def load(frames: dict[str, pd.DataFrame], unified: pd.DataFrame) -> None:
    conn = _connect()
    log.info("Snowflake connection established.")

    try:
        log.info("=== Loading RAW tables ===")
        for src_name, (table_name, renames) in RAW_TABLE_MAP.items():
            df = frames[src_name].rename(columns=renames) if renames else frames[src_name]
            _truncate_and_load(conn, df, _RAW, table_name)

        log.info("=== Loading ANALYTICS.CUSTOMER_EVENT_LOG ===")
        # load_timestamp has a Snowflake DEFAULT; drop it so Snowflake sets it server-side
        unified_load = unified.drop(columns=["load_timestamp"], errors="ignore")
        _truncate_and_load(conn, unified_load, _ANA, "CUSTOMER_EVENT_LOG")

    finally:
        conn.close()
        log.info("Snowflake connection closed.")


def verify() -> None:
    """Query CUSTOMER_EVENT_LOG and print validation stats."""
    conn = _connect()
    db   = _DB()

    try:
        with conn.cursor() as cur:
            # 1. Total row count
            cur.execute(f"SELECT COUNT(*) FROM {db}.{_ANA}.CUSTOMER_EVENT_LOG")
            total = cur.fetchone()[0]

            # 2. Friction candidate stats
            cur.execute(
                f"SELECT COUNT(DISTINCT CUSTOMER_ID) "
                f"FROM {db}.{_ANA}.CUSTOMER_EVENT_LOG "
                f"WHERE IS_FRICTION_CANDIDATE = TRUE"
            )
            fric_customers = cur.fetchone()[0]

            cur.execute(
                f"SELECT COUNT(*) FROM {db}.{_ANA}.CUSTOMER_EVENT_LOG "
                f"WHERE IS_FRICTION_CANDIDATE = TRUE"
            )
            fric_rows = cur.fetchone()[0]

            # 3. Null text_content (expected: online_events rows only)
            cur.execute(
                f"SELECT COUNT(*) FROM {db}.{_ANA}.CUSTOMER_EVENT_LOG "
                f"WHERE TEXT_CONTENT IS NULL"
            )
            null_text = cur.fetchone()[0]

            # 4. Null check — no nulls in PK / timestamp columns
            cur.execute(
                f"SELECT COUNT(*) FROM {db}.{_ANA}.CUSTOMER_EVENT_LOG "
                f"WHERE EVENT_ID IS NULL OR CUSTOMER_ID IS NULL OR EVENT_TIMESTAMP IS NULL"
            )
            null_pk = cur.fetchone()[0]

            # 5. Sample rows
            cur.execute(
                f"SELECT EVENT_ID, CUSTOMER_ID, CHANNEL, EVENT_TIMESTAMP, "
                f"PRODUCT_INVOLVED, ISSUE_CATEGORY, RESOLVED_FLAG, IS_FRICTION_CANDIDATE, REGION "
                f"FROM {db}.{_ANA}.CUSTOMER_EVENT_LOG "
                f"WHERE IS_FRICTION_CANDIDATE = TRUE "
                f"ORDER BY EVENT_TIMESTAMP DESC "
                f"LIMIT 5"
            )
            sample_rows = cur.fetchall()
            sample_cols = [d[0] for d in cur.description]

        print("\n=== CUSTOMER_EVENT_LOG Verification ===")
        print(f"  Total rows:                      {total:>10,}  (expected ~49,000)")
        print(f"  Friction candidate customers:    {fric_customers:>10,}  (expected ~1,500)")
        print(f"  Friction candidate rows:         {fric_rows:>10,}")
        print(f"  Null TEXT_CONTENT rows:          {null_text:>10,}  (expected ~11,000 — online only)")
        print(f"  Null PK/timestamp rows:          {null_pk:>10,}  (expected 0)")

        print("\n  Sample 5 friction rows:")
        sample_df = pd.DataFrame(sample_rows, columns=sample_cols)
        print(sample_df.to_string(index=False, max_colwidth=40))

    finally:
        conn.close()


# ── Dry run (no Snowflake) ─────────────────────────────────────────────────────
def _dry_run_stats(frames: dict[str, pd.DataFrame], unified: pd.DataFrame) -> None:
    print("\n=== DRY RUN — Snowflake credentials not set ===")
    print("  (Set SNOWFLAKE_ACCOUNT / USER / PASSWORD in .env to load)\n")
    print("  Source row counts:")
    for name, df in frames.items():
        print(f"    {name:<22} {len(df):>7,}")
    print(f"\n  Unified CUSTOMER_EVENT_LOG preview:")
    print(f"    Total rows:            {len(unified):>7,}")
    print(f"    Friction rows:         {unified['is_friction_candidate'].sum():>7,}")
    print(f"    Null text_content:     {unified['text_content'].isna().sum():>7,}")
    print(f"    Channels: {unified['channel'].value_counts().to_dict()}")
    print(f"\n  Sample 5 rows (friction=True):")
    sample = unified[unified["is_friction_candidate"]].head(5)
    print(sample[["channel", "customer_id", "event_timestamp",
                  "product_involved", "issue_category",
                  "resolved_flag", "is_friction_candidate"]].to_string(index=False))


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("ATLAS Phase 2 — ETL Load")

    frames  = ingest()
    unified = normalize(frames)

    # Fall back to dry-run if any credential is missing
    creds_present = all(
        os.getenv(k) for k in ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD"]
    )

    if creds_present:
        load(frames, unified)
        verify()
    else:
        _dry_run_stats(frames, unified)
