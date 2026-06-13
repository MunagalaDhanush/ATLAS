"""
ATLAS startup guard — checks for atlas.duckdb and runs the full pipeline if absent.
Called once at Home.py startup before any page renders.
"""


def ensure_data_ready():
    import duckdb
    import streamlit as st
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    db_path = root / "data" / "atlas.duckdb"

    needs_setup = False
    if not db_path.exists():
        needs_setup = True
    else:
        try:
            con = duckdb.connect(str(db_path))
            count = con.execute(
                "SELECT COUNT(*) FROM analytics.friction_hotspots"
            ).fetchone()[0]
            con.close()
            if count == 0:
                needs_setup = True
        except Exception:
            needs_setup = True

    if not needs_setup:
        return

    with st.spinner(
        "First run: building ATLAS data pipeline. "
        "Takes about 90 seconds..."
    ):
        import sys
        import os

        # Set working directory to project root for all scripts
        original_dir = os.getcwd()
        os.chdir(str(root))
        sys.path.insert(0, str(root))

        # Create directories
        (root / "data" / "raw").mkdir(parents=True, exist_ok=True)
        (root / "data" / "processed").mkdir(parents=True, exist_ok=True)
        (root / "data" / "dashboard").mkdir(parents=True, exist_ok=True)

        try:
            import importlib.util

            def run_module(path):
                spec = importlib.util.spec_from_file_location(
                    "module", str(root / path)
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

            st.write("Generating synthetic data...")
            run_module("generate_synthetic_data.py")

            st.write("Running ETL pipeline...")
            run_module("src/02_etl_pipeline/load_duckdb.py")

            st.write("Building customer journeys...")
            run_module("src/03_journey_stitcher/journey_stitcher.py")

            st.write("Detecting friction episodes...")
            run_module("src/04_friction_detector/friction_detector.py")

            st.write("Aggregating KPIs...")
            run_module("src/06_kpi_monitor/kpi_aggregator.py")

            st.write("Running ARIMA forecasts...")
            run_module("src/06_kpi_monitor/kpi_arima_monitor.py")

            st.write("Scoring friction hotspots...")
            run_module("src/07_friction_scoring/friction_scorer.py")

            st.write("Preparing dashboard data...")
            run_module("src/10_dashboard/export_for_powerbi.py")

            # Skip real Groq on cold start — saves API quota
            _create_llm_fallback(str(db_path))

        except Exception as e:
            st.error(f"Pipeline error: {e}")
            raise
        finally:
            os.chdir(original_dir)

    st.success("ATLAS ready.")
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
                COUNT(*) as event_count,
                AVG(sentiment_score) as avg_sentiment_score,
                AVG(CASE WHEN unresolved_issue THEN 1.0 ELSE 0.0 END)
                    as unresolved_rate
            FROM analytics.llm_insights
            GROUP BY theme
        """)
    except Exception:
        pass
    finally:
        con.close()
