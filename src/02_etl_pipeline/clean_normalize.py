"""
ATLAS ETL — Stage 2: Clean & Normalize
Transforms 5 source DataFrames into the unified CUSTOMER_EVENT_LOG schema.

Key mappings:
  - channel:        call / branch / online / mobile / survey
  - issue_category: visit_purpose and event_type mapped to the call-center enum
  - resolved_flag:  source-specific resolution field, or NPS score >= 7 for surveys
  - text_content:   first non-null of transcript_text, banker_notes, feedback_text, open_response
  - is_friction_candidate: True if customer appears in 2+ channels within any 72-hour window
"""

import uuid
import logging
from datetime import timedelta

import pandas as pd

log = logging.getLogger(__name__)

# ── Issue category crosswalks ──────────────────────────────────────────────────
VISIT_PURPOSE_MAP = {
    "account_opening":    "balance_inquiry",
    "dispute_resolution": "fraud_dispute",
    "loan_inquiry":       "balance_inquiry",
    "card_replacement":   "account_locked",
    "wire_transfer":      "payment_failed",
    "general_inquiry":    "balance_inquiry",
}

ONLINE_EVENT_MAP = {
    "page_view":           "balance_inquiry",
    "error_page":          "declined_transaction",
    "form_abandon":        "payment_failed",
    "chat_initiated":      "balance_inquiry",
    "logout_frustration":  "account_locked",
}

MOBILE_EVENT_MAP = {
    "app_crash":        "declined_transaction",
    "feature_error":    "declined_transaction",
    "in_app_feedback":  "balance_inquiry",
    "chat_initiated":   "balance_inquiry",
    "force_close":      "account_locked",
}

FALLBACK_ISSUE = "balance_inquiry"

# ── Helpers ────────────────────────────────────────────────────────────────────
def _uuids(n: int) -> list[str]:
    return [str(uuid.uuid4()) for _ in range(n)]


# ── Per-source mappers ─────────────────────────────────────────────────────────
def _map_call_center(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "event_id":        _uuids(len(df)),
        "customer_id":     df["customer_id"].values,
        "channel":         "call",
        "event_timestamp": df["call_timestamp"].values,
        "product_involved": df["product_involved"].values,
        "issue_category":  df["issue_category"].values,
        "resolved_flag":   df["agent_resolution"].values,
        "text_content":    df["transcript_text"].values,
        "region":          df["region"].values,
    })


def _map_branch(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "event_id":        _uuids(len(df)),
        "customer_id":     df["customer_id"].values,
        "channel":         "branch",
        "event_timestamp": df["visit_timestamp"].values,
        "product_involved": df["product_involved"].values,
        "issue_category":  df["visit_purpose"].map(VISIT_PURPOSE_MAP).fillna(FALLBACK_ISSUE).values,
        "resolved_flag":   df["resolved_flag"].values,
        "text_content":    df["banker_notes"].values,
        "region":          df["region"].values,
    })


def _map_online(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "event_id":        _uuids(len(df)),
        "customer_id":     df["customer_id"].values,
        "channel":         "online",
        "event_timestamp": df["event_timestamp"].values,
        "product_involved": df["product_involved"].values,
        "issue_category":  df["event_type"].map(ONLINE_EVENT_MAP).fillna(FALLBACK_ISSUE).values,
        "resolved_flag":   df["session_resolved"].values,
        "text_content":    [None] * len(df),   # online channel has no free-text field
        "region":          df["region"].values,
    })


def _map_mobile(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "event_id":        _uuids(len(df)),
        "customer_id":     df["customer_id"].values,
        "channel":         "mobile",
        "event_timestamp": df["event_timestamp"].values,
        "product_involved": df["product_involved"].values,
        "issue_category":  df["event_type"].map(MOBILE_EVENT_MAP).fillna(FALLBACK_ISSUE).values,
        "resolved_flag":   df["resolved_flag"].values,
        "text_content":    df["feedback_text"].values,
        "region":          df["region"].values,
    })


def _map_nps(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "event_id":        _uuids(len(df)),
        "customer_id":     df["customer_id"].values,
        "channel":         "survey",
        "event_timestamp": df["survey_timestamp"].values,
        "product_involved": df["product_involved"].values,
        "issue_category":  FALLBACK_ISSUE,        # surveys have no issue category
        "resolved_flag":   (df["nps_score"] >= 7).values,  # promoter/passive = resolved
        "text_content":    df["open_response"].values,
        "region":          df["region"].values,
    })


MAPPERS = {
    "call_center_logs": _map_call_center,
    "branch_visits":    _map_branch,
    "online_events":    _map_online,
    "mobile_events":    _map_mobile,
    "nps_surveys":      _map_nps,
}


# ── Friction detection ─────────────────────────────────────────────────────────
def _detect_friction(unified: pd.DataFrame, window_hours: int = 72) -> pd.Series:
    """
    Mark is_friction_candidate=True for every row whose customer_id appears
    in 2+ distinct non-survey channels within any rolling 72-hour window.
    """
    log.info("Detecting friction candidates...")
    window = timedelta(hours=window_hours)

    channel_events = (
        unified[unified["channel"] != "survey"][["customer_id", "channel", "event_timestamp"]]
        .copy()
    )

    friction_customers: set[str] = set()

    for cid, grp in channel_events.groupby("customer_id", sort=False):
        if grp["channel"].nunique() < 2:
            continue

        rows = grp.sort_values("event_timestamp")
        timestamps = rows["event_timestamp"].tolist()
        channels   = rows["channel"].tolist()
        n = len(timestamps)

        for i in range(n):
            seen = {channels[i]}
            for j in range(i + 1, n):
                if timestamps[j] - timestamps[i] > window:
                    break
                seen.add(channels[j])
                if len(seen) >= 2:
                    friction_customers.add(cid)
                    break
            if cid in friction_customers:
                break

    log.info(f"Friction candidates: {len(friction_customers):,} unique customers")
    return unified["customer_id"].isin(friction_customers)


# ── Public entry point ─────────────────────────────────────────────────────────
def normalize(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return a single unified DataFrame conforming to CUSTOMER_EVENT_LOG schema."""
    parts = []
    for name, mapper in MAPPERS.items():
        if name not in frames:
            log.warning(f"Source '{name}' missing — skipping.")
            continue
        mapped = mapper(frames[name]).reset_index(drop=True)
        log.info(f"[{name}] {len(mapped):,} rows mapped  channel={mapped['channel'].iloc[0]}")
        parts.append(mapped)

    unified = pd.concat(parts, ignore_index=True)

    # Replace empty strings with None so Snowflake stores proper NULLs
    unified["text_content"] = unified["text_content"].replace("", None)

    unified["is_friction_candidate"] = _detect_friction(unified)
    unified["load_timestamp"] = pd.Timestamp.now("UTC").tz_convert(None)

    fric_rows = int(unified["is_friction_candidate"].sum())
    log.info(
        f"Normalization complete — {len(unified):,} unified rows | "
        f"{fric_rows:,} friction rows"
    )
    return unified


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ingest import ingest

    frames  = ingest()
    unified = normalize(frames)

    print("\nUnified schema dtypes:")
    print(unified.dtypes.to_string())
    print(f"\nTotal rows:        {len(unified):,}")
    print(f"Friction rows:     {unified['is_friction_candidate'].sum():,}")
    print(f"Null text_content: {unified['text_content'].isna().sum():,}")
    print("\nSample (5 rows):")
    print(unified[["channel", "customer_id", "event_timestamp",
                   "product_involved", "issue_category",
                   "resolved_flag", "is_friction_candidate"]].head().to_string(index=False))
