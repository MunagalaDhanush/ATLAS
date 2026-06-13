"""
ATLAS startup guard — diagnostic version with verbose logging.
Data generation is inlined to avoid importlib path ambiguity on Streamlit Cloud.
"""

from pathlib import Path


def _generate_data(root: Path) -> int:
    """Generate synthetic banking CSVs directly into root/data/raw/."""
    import pandas as pd
    import numpy as np
    import uuid
    from datetime import datetime, timedelta
    import random

    raw_dir = root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    END_DATE = datetime.now()
    START_DATE = END_DATE - timedelta(weeks=26)
    PRODUCTS = ["checking", "savings", "credit_card", "mortgage", "auto_loan"]
    ISSUES = ["declined_transaction", "balance_inquiry", "fraud_dispute",
              "payment_failed", "account_locked"]
    REGIONS = ["Northeast", "Southeast", "Midwest", "West", "Southwest"]
    N_CUSTOMERS = 10000
    FRICTION_COUNT = 1500

    random.seed(42)
    np.random.seed(42)

    all_ids = [str(uuid.uuid4()) for _ in range(N_CUSTOMERS)]
    friction_ids = set(random.sample(all_ids, FRICTION_COUNT))

    def rand_ts():
        delta = END_DATE - START_DATE
        return START_DATE + timedelta(seconds=random.randint(0, int(delta.total_seconds())))

    CALL_TEMPLATES = [
        "Customer called about {issue} on {product} account. Amount: ${amt}.",
        "Called regarding {issue}. Account balance ${amt}. Escalated to supervisor.",
        "Inquiry about {issue} on {product}. Customer frustrated. Amount: ${amt}.",
        "Customer reported {issue}. Said amount of ${amt} was affected.",
        "Called to dispute {issue} on {product} account totaling ${amt}.",
    ]
    BRANCH_TEMPLATES = [
        "Customer visited regarding {issue} on {product}. Amount: ${amt}.",
        "Branch visit: {issue} complaint. Customer upset. ${amt} at stake.",
        "In-person inquiry about {issue}. Reviewed {product} account, ${amt}.",
        "Customer came in about {issue}. Referred to {product} team. ${amt}.",
    ]
    MOBILE_TEMPLATES = [
        "App issue: {issue} not resolved. Tried 3 times. ${amt} affected.",
        "Mobile feedback: {issue} on {product}. Very frustrated. ${amt}.",
        "Submitted complaint via app about {issue}. Amount ${amt}.",
        "App crash during {issue} resolution. ${amt} pending.",
    ]
    NPS_TEMPLATES = [
        "Terrible experience with {issue}. Will not recommend. ${amt} lost.",
        "Had {issue} problem, took days to fix. ${amt} was affected.",
        "Great service resolving my {issue} issue. ${amt} recovered quickly.",
        "Neutral experience. {issue} was handled ok. ${amt} processed.",
        "Very happy with how {issue} was resolved. ${amt} restored fast.",
    ]

    def make_text(templates, issue, product, amt):
        t = random.choice(templates)
        return t.format(
            issue=issue.replace("_", " "),
            product=product.replace("_", " "),
            amt=f"{amt:,.2f}",
        )

    # ── Call center logs ───────────────────────────────────────────────────────
    rows = []
    for cid in all_ids:
        is_friction = cid in friction_ids
        n = random.randint(2, 4) if is_friction else random.randint(1, 2)
        anchor = rand_ts() if is_friction else None
        for _ in range(n):
            ts = (anchor + timedelta(hours=random.uniform(0, 71))) if anchor else rand_ts()
            prod = random.choice(PRODUCTS)
            issue = random.choice(ISSUES)
            amt = round(random.uniform(50, 5000), 2)
            rows.append({
                "customer_id":      cid,
                "call_id":          str(uuid.uuid4()),
                "call_timestamp":   ts.strftime("%Y-%m-%d %H:%M:%S"),
                "call_duration_sec": random.randint(60, 900),
                "ivr_resolution":   random.random() > 0.7,
                "agent_resolution": random.random() > (0.8 if is_friction else 0.4),
                "product_involved": prod,
                "issue_category":   issue,
                "transcript_text":  make_text(CALL_TEMPLATES, issue, prod, amt),
                "region":           random.choice(REGIONS),
            })
    pd.DataFrame(rows).to_csv(str(raw_dir / "call_center_logs.csv"), index=False)

    # ── Branch visits ──────────────────────────────────────────────────────────
    rows = []
    for cid in all_ids:
        is_friction = cid in friction_ids
        n = random.randint(1, 2) if is_friction else random.randint(0, 1)
        anchor = rand_ts() if is_friction else None
        for _ in range(n):
            ts = (anchor + timedelta(hours=random.uniform(1, 71))) if anchor else rand_ts()
            prod = random.choice(PRODUCTS)
            issue = random.choice(ISSUES)
            amt = round(random.uniform(100, 8000), 2)
            rows.append({
                "customer_id":    cid,
                "visit_id":       str(uuid.uuid4()),
                "visit_timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "branch_id":      f"BR{random.randint(100, 999)}",
                "visit_purpose":  issue,
                "product_involved": prod,
                "resolved_flag":  not is_friction or random.random() > 0.7,
                "banker_notes":   make_text(BRANCH_TEMPLATES, issue, prod, amt),
                "region":         random.choice(REGIONS),
            })
    pd.DataFrame(rows).to_csv(str(raw_dir / "branch_visits.csv"), index=False)

    # ── Online events ──────────────────────────────────────────────────────────
    rows = []
    EVENT_TYPES = ["page_view", "error_page", "form_abandon", "chat_initiated", "logout_frustration"]
    for cid in random.sample(all_ids, 11000):
        rows.append({
            "customer_id":    cid,
            "session_id":     str(uuid.uuid4()),
            "event_timestamp": rand_ts().strftime("%Y-%m-%d %H:%M:%S"),
            "event_type":     random.choice(EVENT_TYPES),
            "page_name":      random.choice(["account", "payments", "transfers", "disputes", "settings"]),
            "product_involved": random.choice(PRODUCTS),
            "session_resolved": random.random() > 0.4,
            "region":         random.choice(REGIONS),
        })
    pd.DataFrame(rows).to_csv(str(raw_dir / "online_events.csv"), index=False)

    # ── Mobile events ──────────────────────────────────────────────────────────
    rows = []
    MOB_TYPES = ["app_crash", "feature_error", "in_app_feedback", "chat_initiated", "force_close"]
    for cid in random.sample(all_ids, 10300):
        is_friction = cid in friction_ids
        prod = random.choice(PRODUCTS)
        issue = random.choice(ISSUES)
        amt = round(random.uniform(50, 3000), 2)
        rows.append({
            "customer_id":    cid,
            "event_id":       str(uuid.uuid4()),
            "event_timestamp": rand_ts().strftime("%Y-%m-%d %H:%M:%S"),
            "event_type":     random.choice(MOB_TYPES),
            "feature_name":   random.choice(["payments", "transfers", "balance", "disputes", "profile"]),
            "product_involved": prod,
            "feedback_text":  make_text(MOBILE_TEMPLATES, issue, prod, amt) if is_friction else "",
            "resolved_flag":  not is_friction or random.random() > 0.7,
            "region":         random.choice(REGIONS),
        })
    pd.DataFrame(rows).to_csv(str(raw_dir / "mobile_events.csv"), index=False)

    # ── NPS surveys ────────────────────────────────────────────────────────────
    rows = []
    for cid in random.sample(all_ids, 10000):
        is_friction = cid in friction_ids
        prod = random.choice(PRODUCTS)
        issue = random.choice(ISSUES)
        amt = round(random.uniform(50, 5000), 2)
        rows.append({
            "customer_id":    cid,
            "survey_id":      str(uuid.uuid4()),
            "survey_timestamp": rand_ts().strftime("%Y-%m-%d %H:%M:%S"),
            "nps_score":      random.randint(0, 5) if is_friction else random.randint(6, 10),
            "csat_score":     random.randint(1, 3) if is_friction else random.randint(3, 5),
            "open_response":  make_text(NPS_TEMPLATES, issue, prod, amt),
            "product_involved": prod,
            "channel_of_last_contact": random.choice(["call", "branch", "online", "mobile"]),
            "region":         random.choice(REGIONS),
        })
    pd.DataFrame(rows).to_csv(str(raw_dir / "nps_surveys.csv"), index=False)

    return len(list(raw_dir.glob("*.csv")))


def ensure_data_ready():
    import duckdb
    import streamlit as st
    import os
    import sys

    root = Path(__file__).resolve().parents[3]
    db_path = root / "data" / "atlas.duckdb"

    # Log environment
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
            # Step 1: inline generation — no importlib, path is guaranteed
            st.write("Generating synthetic data...")
            csv_count = _generate_data(root)
            st.write(f"OK: Synthetic data -- {csv_count} CSVs written to {root / 'data' / 'raw'}")

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
