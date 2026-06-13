"""
ATLAS ETL — DuckDB Setup and Load (replaces load_snowflake.py)
Creates data/atlas.duckdb and populates:
  - raw.*          : 5 source tables (one per CSV)
  - analytics.customer_event_log : unified 49k-row table

Connection: duckdb.connect(DB_PATH)  — no account, warehouse, or cloud needed.
"""

import sys
import logging
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest import ingest
from clean_normalize import normalize

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

_ROOT   = Path(__file__).resolve().parents[2]
DB_PATH = str(_ROOT / "data" / "atlas.duckdb")


# ── Schema creation ────────────────────────────────────────────────────────────
_DDL = [
    "CREATE SCHEMA IF NOT EXISTS raw",
    "CREATE SCHEMA IF NOT EXISTS analytics",
]


def _create_schemas(con: duckdb.DuckDBPyConnection) -> None:
    for stmt in _DDL:
        con.execute(stmt)
    log.info("Schemas ready: raw, analytics")


# ── Generic loader ─────────────────────────────────────────────────────────────
def _load_df(
    con: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    schema: str,
    table: str,
    renames: dict | None = None,
) -> int:
    if renames:
        df = df.rename(columns=renames)
    full = f"{schema}.{table}"
    con.register("_load_tmp", df)
    con.execute(f"CREATE OR REPLACE TABLE {full} AS SELECT * FROM _load_tmp")
    con.unregister("_load_tmp")
    count = con.execute(f"SELECT COUNT(*) FROM {full}").fetchone()[0]
    log.info(f"  [{full}] {count:,} rows")
    return count


# ── RAW table map ──────────────────────────────────────────────────────────────
# Source name -> (table name, column renames)
RAW_MAP = {
    "call_center_logs": ("call_center_logs", {"call_duration_seconds": "call_duration_sec"}),
    "branch_visits":    ("branch_visits",    {}),
    "online_events":    ("online_events",    {}),
    "mobile_events":    ("mobile_events",    {}),
    "nps_surveys":      ("nps_surveys",      {}),
}


def load_raw(con: duckdb.DuckDBPyConnection, frames: dict[str, pd.DataFrame]) -> None:
    log.info("Loading RAW tables...")
    for src, (table, renames) in RAW_MAP.items():
        _load_df(con, frames[src], "raw", table, renames or None)


def load_analytics(con: duckdb.DuckDBPyConnection, unified: pd.DataFrame) -> None:
    log.info("Loading analytics.customer_event_log...")
    _load_df(con, unified, "analytics", "customer_event_log")


# ── Verification ───────────────────────────────────────────────────────────────
def verify(con: duckdb.DuckDBPyConnection) -> None:
    print("\n=== DuckDB Load Verification ===")

    tables = con.execute("""
        SELECT table_schema, table_name,
               (SELECT COUNT(*) FROM information_schema.tables t2
                WHERE t2.table_schema = t.table_schema AND t2.table_name = t.table_name) AS exists_flag
        FROM information_schema.tables t
        WHERE table_schema IN ('raw', 'analytics')
        ORDER BY table_schema, table_name
    """).df()

    all_tables = [
        ("raw",       "call_center_logs"),
        ("raw",       "branch_visits"),
        ("raw",       "online_events"),
        ("raw",       "mobile_events"),
        ("raw",       "nps_surveys"),
        ("analytics", "customer_event_log"),
    ]

    total = 0
    for schema, tbl in all_tables:
        count = con.execute(f"SELECT COUNT(*) FROM {schema}.{tbl}").fetchone()[0]
        total += count
        print(f"  {schema}.{tbl:<30} {count:>8,} rows")

    print(f"  {'TOTAL':<36} {total:>8,} rows")

    fric = con.execute(
        "SELECT COUNT(*) FROM analytics.customer_event_log WHERE is_friction_candidate"
    ).fetchone()[0]
    null_txt = con.execute(
        "SELECT COUNT(*) FROM analytics.customer_event_log WHERE text_content IS NULL"
    ).fetchone()[0]
    print(f"\n  Friction rows:        {fric:>8,}")
    print(f"  Null text_content:    {null_txt:>8,}  (online_events only)")


# ── Entry point ────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("ATLAS Phase 2 — DuckDB Load")
    log.info(f"Database: {DB_PATH}")

    frames  = ingest()
    unified = normalize(frames)

    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH)

    try:
        _create_schemas(con)
        load_raw(con, frames)
        load_analytics(con, unified)
        verify(con)
    finally:
        con.close()

    log.info("Done.")


if __name__ == "__main__":
    main()
