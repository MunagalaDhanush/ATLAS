"""
ATLAS startup guard — diagnostic version with verbose logging.
"""


def ensure_data_ready():
    import duckdb
    import streamlit as st
    from pathlib import Path
    import os, sys

    root = Path(__file__).resolve().parents[3]
    db_path = root / "data" / "atlas.duckdb"

    # Log environment for debugging
    st.write(f"DEBUG: root = {root}")
    st.write(f"DEBUG: db_path = {db_path}")
    st.write(f"DEBUG: db exists = {db_path.exists()}")
    st.write(f"DEBUG: cwd = {os.getcwd()}")

    # Write permission check
    test_file = root / "data" / "test_write.txt"
    try:
        test_file.write_text("test")
        test_file.unlink()
        st.write("DEBUG: Write permission OK")
    except Exception as e:
        st.write(f"DEBUG: NO WRITE PERMISSION - {e}")

    needs_setup = False
    if not db_path.exists():
        st.write("DEBUG: DB does not exist - running pipeline")
        needs_setup = True
    else:
        st.write("DEBUG: DB exists - checking tables")
        try:
            con = duckdb.connect(str(db_path))
            tables = con.execute("SHOW ALL TABLES").df()
            st.write(f"DEBUG: Tables found: {tables['name'].tolist()}")
            try:
                count = con.execute(
                    "SELECT COUNT(*) FROM analytics.friction_hotspots"
                ).fetchone()[0]
                st.write(f"DEBUG: friction_hotspots count = {count}")
                if count == 0:
                    needs_setup = True
            except Exception as e:
                st.write(f"DEBUG: friction_hotspots error = {e}")
                needs_setup = True
            con.close()
        except Exception as e:
            st.write(f"DEBUG: DB connection error = {e}")
            needs_setup = True

    if not needs_setup:
        st.write("DEBUG: Data ready - skipping pipeline")
        return

    with st.spinner("Building pipeline..."):
        original_dir = os.getcwd()
        os.chdir(str(root))
        sys.path.insert(0, str(root))

        (root / "data" / "raw").mkdir(parents=True, exist_ok=True)
        (root / "data" / "processed").mkdir(parents=True, exist_ok=True)
        (root / "data" / "dashboard").mkdir(parents=True, exist_ok=True)

        def run_module(path, label):
            import importlib.util
            st.write(f"Running: {label}")
            try:
                spec = importlib.util.spec_from_file_location(
                    "module", str(root / path)
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                st.write(f"OK: {label}")
            except Exception as e:
                st.write(f"FAILED: {label} -- {e}")
                raise

        try:
            run_module("generate_synthetic_data.py", "Synthetic data")

            csv_count = len(list((root / "data" / "raw").glob("*.csv")))
            st.write(f"DEBUG: CSVs in data/raw = {csv_count}")

            run_module("src/02_etl_pipeline/load_duckdb.py", "ETL")
            run_module("src/03_journey_stitcher/journey_stitcher.py", "Journeys")
            run_module("src/04_friction_detector/friction_detector.py", "Friction")
            run_module("src/06_kpi_monitor/kpi_aggregator.py", "KPI aggregator")
            run_module("src/06_kpi_monitor/kpi_arima_monitor.py", "ARIMA")
            run_module("src/07_friction_scoring/friction_scorer.py", "Scoring")
            run_module("src/10_dashboard/export_for_powerbi.py", "Dashboard export")
            _create_llm_fallback(str(db_path))
            st.write("Pipeline complete")

            # Post-pipeline verification
            con = duckdb.connect(str(db_path))
            try:
                tables = con.execute("SHOW ALL TABLES").df()
                st.write(f"DEBUG: Final tables = {tables['name'].tolist()}")
                hs_count = con.execute(
                    "SELECT COUNT(*) FROM analytics.friction_hotspots"
                ).fetchone()[0]
                st.write(f"DEBUG: friction_hotspots rows = {hs_count}")
            finally:
                con.close()

        except Exception as e:
            st.error(f"Pipeline failed: {e}")
            import traceback
            st.code(traceback.format_exc())
        finally:
            os.chdir(original_dir)

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
