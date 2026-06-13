from pathlib import Path
import streamlit as st
import duckdb

def ensure_data_ready():
    root = Path(__file__).resolve().parents[3]
    db_path = root / "data" / "atlas.duckdb"

    if not db_path.exists():
        st.error(
            "Database not found at: " + str(db_path) +
            " — ensure data/atlas.duckdb is committed to the repo."
        )
        st.stop()
        return

    try:
        con = duckdb.connect(str(db_path))
        count = con.execute(
            "SELECT COUNT(*) FROM analytics.friction_hotspots"
        ).fetchone()[0]
        con.close()
        if count > 0:
            return
        else:
            st.error("Database exists but is empty. Re-push atlas.duckdb.")
            st.stop()
    except Exception as e:
        st.error(f"Database error: {e}")
        st.stop()
