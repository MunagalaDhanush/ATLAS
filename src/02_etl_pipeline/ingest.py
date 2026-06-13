"""
ATLAS ETL — Stage 1: Ingest
Reads 5 source CSVs from data/raw/, validates schema and key constraints,
and returns a dict of clean DataFrames.
"""

import logging
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

# Per-source validation specs
SOURCES = {
    "call_center_logs": {
        "file": "call_center_logs.csv",
        "required_cols": [
            "customer_id", "call_id", "call_timestamp", "call_duration_seconds",
            "ivr_resolution", "agent_resolution", "product_involved",
            "issue_category", "transcript_text", "region",
        ],
        "timestamp_cols": ["call_timestamp"],
        "bool_cols":      ["ivr_resolution", "agent_resolution"],
        "not_null":       ["customer_id", "call_id", "call_timestamp"],
    },
    "branch_visits": {
        "file": "branch_visits.csv",
        "required_cols": [
            "customer_id", "visit_id", "visit_timestamp", "branch_id",
            "visit_purpose", "product_involved", "resolved_flag", "banker_notes", "region",
        ],
        "timestamp_cols": ["visit_timestamp"],
        "bool_cols":      ["resolved_flag"],
        "not_null":       ["customer_id", "visit_id", "visit_timestamp"],
    },
    "online_events": {
        "file": "online_events.csv",
        "required_cols": [
            "customer_id", "session_id", "event_timestamp", "event_type",
            "page_name", "product_involved", "session_resolved", "region",
        ],
        "timestamp_cols": ["event_timestamp"],
        "bool_cols":      ["session_resolved"],
        "not_null":       ["customer_id", "session_id", "event_timestamp"],
    },
    "mobile_events": {
        "file": "mobile_events.csv",
        "required_cols": [
            "customer_id", "event_id", "event_timestamp", "event_type",
            "feature_name", "product_involved", "feedback_text", "resolved_flag", "region",
        ],
        "timestamp_cols": ["event_timestamp"],
        "bool_cols":      ["resolved_flag"],
        "not_null":       ["customer_id", "event_id", "event_timestamp"],
    },
    "nps_surveys": {
        "file": "nps_surveys.csv",
        "required_cols": [
            "customer_id", "survey_id", "survey_timestamp", "nps_score",
            "csat_score", "open_response", "product_involved",
            "channel_of_last_contact", "region",
        ],
        "timestamp_cols": ["survey_timestamp"],
        "bool_cols":      [],
        "not_null":       ["customer_id", "survey_id", "survey_timestamp", "nps_score"],
    },
}


def _validate(name: str, df: pd.DataFrame, spec: dict) -> pd.DataFrame:
    missing_cols = [c for c in spec["required_cols"] if c not in df.columns]
    if missing_cols:
        raise ValueError(f"[{name}] Missing required columns: {missing_cols}")

    for col in spec["timestamp_cols"]:
        df[col] = pd.to_datetime(df[col])

    for col in spec["bool_cols"]:
        df[col] = df[col].astype(bool)

    null_violations = {}
    for col in spec["not_null"]:
        n = int(df[col].isna().sum())
        if n > 0:
            null_violations[col] = n
    if null_violations:
        log.warning(f"[{name}] Nulls in non-nullable columns: {null_violations}")

    log.info(f"[{name}] OK — {len(df):,} rows, {len(df.columns)} cols")
    return df


def ingest() -> dict[str, pd.DataFrame]:
    """Read and validate all source CSVs. Raises if a file is missing or schema is wrong."""
    frames: dict[str, pd.DataFrame] = {}
    for name, spec in SOURCES.items():
        path = RAW_DIR / spec["file"]
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {path}")
        df = pd.read_csv(path, low_memory=False)
        frames[name] = _validate(name, df, spec)

    total = sum(len(df) for df in frames.values())
    log.info(f"Ingest complete — {len(frames)} sources, {total:,} total rows")
    return frames


if __name__ == "__main__":
    frames = ingest()
    print("\nRow counts:")
    for name, df in frames.items():
        print(f"  {name:<22} {len(df):>7,}")
