"""
ATLAS Streamlit — Cached DuckDB query functions.
All queries use read-only connection; no writes from the dashboard.
"""

from __future__ import annotations
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "atlas.duckdb"

load_dotenv(Path(__file__).resolve().parents[3] / ".env")


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(_DB_PATH), read_only=True)


# ── KPI weekly summary ────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_kpi_weekly() -> pd.DataFrame:
    with _con() as con:
        return con.execute(
            "SELECT * FROM analytics.kpi_weekly_summary ORDER BY week_start"
        ).df()


# ── KPI alerts ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_kpi_alerts() -> pd.DataFrame:
    with _con() as con:
        return con.execute(
            "SELECT * FROM analytics.kpi_alerts ORDER BY alert_fired DESC, ABS(pct_change) DESC"
        ).df()


# ── Friction hotspots ─────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_friction_hotspots() -> pd.DataFrame:
    with _con() as con:
        return con.execute(
            "SELECT * FROM analytics.friction_hotspots ORDER BY priority_score DESC"
        ).df()


# ── LLM theme summary ─────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_llm_theme_summary() -> pd.DataFrame:
    with _con() as con:
        return con.execute(
            "SELECT * FROM analytics.llm_theme_summary ORDER BY event_count DESC"
        ).df()


# ── LLM insights (raw, 500 rows) ──────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_llm_insights() -> pd.DataFrame:
    with _con() as con:
        return con.execute(
            "SELECT * FROM analytics.llm_insights"
        ).df()


# ── Customer journeys (full) ──────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_customer_journeys() -> pd.DataFrame:
    with _con() as con:
        return con.execute(
            "SELECT * FROM analytics.customer_journeys"
        ).df()


# ── Journey aggregates for dashboard ─────────────────────────────────────────
@st.cache_data(ttl=300)
def get_journey_stats() -> dict:
    with _con() as con:
        row = con.execute("""
            SELECT
                COUNT(*)                                                AS total_episodes,
                SUM(CASE WHEN is_friction_episode THEN 1 END)          AS friction_episodes,
                AVG(friction_score)                                     AS avg_friction_score,
                AVG(episode_duration_hours)                             AS avg_duration_hours,
                AVG(CASE WHEN is_friction_episode
                         THEN episode_duration_hours END)               AS avg_friction_duration,
                COUNT(DISTINCT customer_id)                             AS unique_customers
            FROM analytics.customer_journeys
        """).fetchone()
        keys = ["total_episodes", "friction_episodes", "avg_friction_score",
                "avg_duration_hours", "avg_friction_duration", "unique_customers"]
        return dict(zip(keys, row))


# ── Channel sentiment from LLM insights ──────────────────────────────────────
# Uses analytics.llm_insights column: unresolved_issue (boolean)
@st.cache_data(ttl=300)
def get_channel_sentiment() -> pd.DataFrame:
    with _con() as con:
        return con.execute("""
            SELECT
                channel,
                AVG(sentiment_score)                                          AS avg_sentiment,
                COUNT(*)                                                       AS event_count,
                SUM(CASE WHEN unresolved_issue = true THEN 1 ELSE 0 END)*1.0
                    / NULLIF(COUNT(*), 0)                                     AS unresolved_rate
            FROM analytics.llm_insights
            GROUP BY channel
            ORDER BY avg_sentiment
        """).df()


# ── Friction by region ────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_friction_by_region() -> pd.DataFrame:
    with _con() as con:
        return con.execute("""
            SELECT
                region,
                COUNT(*)                                                        AS total_episodes,
                SUM(CASE WHEN is_friction_episode THEN 1 END)                  AS friction_episodes,
                AVG(friction_score)                                             AS avg_friction_score,
                SUM(CASE WHEN is_friction_episode THEN 1 END)*1.0/COUNT(*)     AS friction_rate
            FROM analytics.customer_journeys
            GROUP BY region
            ORDER BY friction_rate DESC
        """).df()


# ── Top channel sequences by friction rate ────────────────────────────────────
@st.cache_data(ttl=300)
def get_top_sequences(limit: int = 10) -> pd.DataFrame:
    with _con() as con:
        return con.execute(f"""
            SELECT
                channel_sequence,
                COUNT(*)                                                       AS episode_count,
                SUM(CASE WHEN is_friction_episode THEN 1 END)                 AS friction_count,
                SUM(CASE WHEN is_friction_episode THEN 1 END)*1.0/COUNT(*)    AS friction_rate
            FROM analytics.customer_journeys
            WHERE channel_sequence IS NOT NULL
            GROUP BY channel_sequence
            HAVING COUNT(*) >= 10
            ORDER BY friction_rate DESC
            LIMIT {limit}
        """).df()


# ── Segment query (used by Segment Explorer page) ─────────────────────────────
# customer_journeys schema: eventually_resolved (bool), dominant_channel, region
# llm_insights schema: unresolved_issue (bool), theme, sentiment_score, urgency_level
@st.cache_data(ttl=120)
def run_segment_query(
    product: str | None = None,
    region: str | None = None,
    channel: str | None = None,
    min_friction_score: float | None = None,
) -> pd.DataFrame:
    _ALLOWED = {
        "product": {"checking", "savings", "credit_card", "mortgage", "auto_loan"},
        "region":  {"Northeast", "Southeast", "Midwest", "Southwest", "West"},
        "channel": {"call", "branch", "online", "mobile"},
    }
    conditions = ["cj.is_friction_episode = true"]
    if product and product in _ALLOWED["product"]:
        conditions.append(f"cj.product_involved = '{product}'")
    if region and region in _ALLOWED["region"]:
        conditions.append(f"cj.region = '{region}'")
    if channel and channel in _ALLOWED["channel"]:
        conditions.append(f"cj.dominant_channel = '{channel}'")
    if min_friction_score is not None:
        conditions.append(f"cj.friction_score >= {float(min_friction_score)}")

    where = " AND ".join(conditions)
    with _con() as con:
        return con.execute(f"""
            SELECT
                cj.customer_id,
                cj.product_involved,
                cj.region,
                cj.dominant_channel,
                cj.friction_score,
                cj.eventually_resolved,
                cj.episode_duration_hours,
                cj.channel_sequence,
                li.theme,
                li.sentiment_score,
                li.urgency_level
            FROM analytics.customer_journeys cj
            LEFT JOIN analytics.llm_insights li ON cj.customer_id = li.customer_id
            WHERE {where}
            ORDER BY cj.friction_score DESC
            LIMIT 500
        """).df()
