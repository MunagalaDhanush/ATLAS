"""
ATLAS startup guard — checks for atlas.duckdb and runs the full pipeline if absent.
Called once at Home.py startup before any page renders.
"""


def ensure_data_ready():
    """
    Checks if atlas.duckdb exists and has data.
    If not, runs the full data generation + ETL pipeline automatically.
    Called once at app startup from Home.py.
    """
    import duckdb
    import os
    from pathlib import Path

    # Find project root
    root = Path(__file__).resolve().parents[3]
    db_path = root / "data" / "atlas.duckdb"

    # Check if DB exists and has data
    if db_path.exists():
        try:
            con = duckdb.connect(str(db_path))
            count = con.execute(
                "SELECT COUNT(*) FROM analytics.customer_event_log"
            ).fetchone()[0]
            con.close()
            if count > 0:
                return  # Data exists, nothing to do
        except Exception:
            pass

    # Data missing — run pipeline
    import streamlit as st
    with st.spinner(
        "First run detected — generating data and building analytics "
        "pipeline. This takes about 2 minutes..."
    ):
        # Create data directory
        (root / "data" / "raw").mkdir(parents=True, exist_ok=True)
        (root / "data" / "processed").mkdir(parents=True, exist_ok=True)
        (root / "data" / "dashboard").mkdir(parents=True, exist_ok=True)

        import subprocess, sys
        scripts = [
            "generate_synthetic_data.py",
            "src/02_etl_pipeline/load_duckdb.py",
            "src/03_journey_stitcher/journey_stitcher.py",
            "src/04_friction_detector/friction_detector.py",
            "src/06_kpi_monitor/kpi_aggregator.py",
            "src/06_kpi_monitor/kpi_arima_monitor.py",
            "src/07_friction_scoring/friction_scorer.py",
            "src/10_dashboard/export_for_powerbi.py",
        ]
        for script in scripts:
            subprocess.run(
                [sys.executable, str(root / script)],
                cwd=str(root),
                capture_output=True,
            )

        # Skip LLM theme extractor on cold start
        # (saves Groq API quota — uses cached fallback)
        _create_llm_fallback(con_path=str(db_path))

    st.success("Data ready. Loading dashboard...")
    st.rerun()


def _create_llm_fallback(con_path: str):
    """Creates minimal llm_insights table if Groq not available."""
    import duckdb
    con = duckdb.connect(con_path)
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS analytics.llm_insights AS
            SELECT
                event_id,
                customer_id,
                channel,
                'general_friction' as theme,
                -0.3 as sentiment_score,
                true as unresolved_issue,
                'medium' as urgency_level,
                'customer needs assistance' as key_phrase,
                CURRENT_TIMESTAMP as processed_at
            FROM analytics.customer_event_log
            WHERE text_content IS NOT NULL
            LIMIT 500
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS analytics.llm_theme_summary AS
            SELECT
                theme,
                COUNT(*) as count,
                AVG(sentiment_score) as avg_sentiment,
                AVG(CASE WHEN unresolved_issue THEN 1.0 ELSE 0.0 END)
                    as pct_unresolved
            FROM analytics.llm_insights
            GROUP BY theme
        """)
    except Exception:
        pass
    finally:
        con.close()
