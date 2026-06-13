"""
ATLAS Airflow DAG — atlas_etl_pipeline
Schedule: @daily

Task graph:
  ingest_sources  ->  normalize_data  ->  load_to_snowflake  ->  validate_load

Each task is independently fault-tolerant:
  - ingest_sources validates CSV schema; fails fast if a file is missing or malformed
  - normalize_data runs the full normalization and pushes row counts via XCom
  - load_to_snowflake performs truncate-and-reload for all 6 Snowflake tables
  - validate_load queries CUSTOMER_EVENT_LOG and asserts expected row count
"""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

log = logging.getLogger(__name__)

ETL_DIR = Path(__file__).resolve().parent   # src/02_etl_pipeline/
EXPECTED_UNIFIED_ROWS = 49_000
ROW_COUNT_TOLERANCE   = 2_000

default_args = {
    "owner":            "atlas",
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
    "start_date":       datetime(2025, 12, 13),
    "email_on_failure": False,
    "email_on_retry":   False,
    "depends_on_past":  False,
}


# ── Task callables ─────────────────────────────────────────────────────────────
def task_ingest_sources(**context) -> dict[str, int]:
    import sys
    sys.path.insert(0, str(ETL_DIR))
    from ingest import ingest

    frames = ingest()
    counts = {name: len(df) for name, df in frames.items()}
    log.info(f"Ingest validated: {counts}")
    context["ti"].xcom_push(key="source_row_counts", value=counts)
    return counts


def task_normalize_data(**context) -> int:
    import sys
    sys.path.insert(0, str(ETL_DIR))
    from ingest import ingest
    from clean_normalize import normalize

    frames  = ingest()
    unified = normalize(frames)

    stats = {
        "total_rows":      len(unified),
        "friction_rows":   int(unified["is_friction_candidate"].sum()),
        "null_text_rows":  int(unified["text_content"].isna().sum()),
    }
    log.info(f"Normalization stats: {stats}")
    context["ti"].xcom_push(key="normalize_stats", value=stats)
    return stats["total_rows"]


def task_load_to_snowflake(**context) -> None:
    import sys
    sys.path.insert(0, str(ETL_DIR))
    from ingest import ingest
    from clean_normalize import normalize
    from load_snowflake import load

    frames  = ingest()
    unified = normalize(frames)
    load(frames, unified)
    log.info("Load to Snowflake complete.")


def task_validate_load(**context) -> int:
    import sys
    sys.path.insert(0, str(ETL_DIR))
    from dotenv import load_dotenv
    load_dotenv(ETL_DIR.parents[1] / ".env")

    try:
        import snowflake.connector
    except ImportError:
        raise ImportError("snowflake-connector-python not installed.")

    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema="ANALYTICS",
        session_parameters={"TIMEZONE": "UTC"},
    )
    db = os.environ.get("SNOWFLAKE_DATABASE", "ATLAS_DB")

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {db}.ANALYTICS.CUSTOMER_EVENT_LOG"
            )
            row_count = cur.fetchone()[0]
    finally:
        conn.close()

    lo = EXPECTED_UNIFIED_ROWS - ROW_COUNT_TOLERANCE
    hi = EXPECTED_UNIFIED_ROWS + ROW_COUNT_TOLERANCE
    if not (lo <= row_count <= hi):
        raise ValueError(
            f"Validation failed: CUSTOMER_EVENT_LOG has {row_count:,} rows, "
            f"expected {lo:,}–{hi:,}."
        )

    log.info(f"Validation passed: {row_count:,} rows in CUSTOMER_EVENT_LOG.")
    context["ti"].xcom_push(key="validated_row_count", value=row_count)
    return row_count


# ── DAG definition ─────────────────────────────────────────────────────────────
with DAG(
    dag_id="atlas_etl_pipeline",
    default_args=default_args,
    schedule_interval="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["atlas", "banking", "etl", "snowflake"],
    description="ATLAS daily ETL: CSV ingest -> normalize -> Snowflake load -> validation",
) as dag:

    ingest_task = PythonOperator(
        task_id="ingest_sources",
        python_callable=task_ingest_sources,
    )

    normalize_task = PythonOperator(
        task_id="normalize_data",
        python_callable=task_normalize_data,
    )

    load_task = PythonOperator(
        task_id="load_to_snowflake",
        python_callable=task_load_to_snowflake,
    )

    validate_task = PythonOperator(
        task_id="validate_load",
        python_callable=task_validate_load,
    )

    ingest_task >> normalize_task >> load_task >> validate_task
