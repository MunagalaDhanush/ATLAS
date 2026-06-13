# ATLAS — Automated Transaction & Lifecycle Analytics System

## Overview

ATLAS is a banking analytics portfolio project that simulates the friction problem every multi-channel bank faces: a customer calls about a declined transaction, never gets resolution, then tries the mobile app, then visits a branch — each interaction is logged in a silo, but no system connects them into a single journey. By the time the NPS survey arrives, trust is already eroded.

ATLAS unifies 49,000 synthetic customer interaction events across four channels (call center, branch, online, mobile) into a single analytical stack. It stitches individual events into episodes using a 72-hour gap threshold, scores episode friction using a multi-rule engine, extracts themes and sentiment from free-text using a live LLM (Groq llama-3.1-8b-instant), forecasts KPI deterioration using ARIMA, and surfaces the highest-priority hotspot segments using a composite scoring model — all backed by DuckDB and exported into a Power BI dashboard.

---

## Key Findings

- **Mobile is the worst-performing channel:** average sentiment -0.849 with 100% unresolved issue rate across all LLM-analysed interactions
- **The online → mobile cross-channel sequence has the highest friction rate at 66.3%** — customers who start online and escalate to mobile are the most likely to churn
- **savings + Northeast + call is the most alarming segment:** 80% unresolved rate with avg friction score 75.2 — the single highest-risk cohort in the portfolio
- **340 high-severity customers (friction_score ≥ 70) account for 45.6% unresolved cases** — less than 1% of the customer base driving outsized operational cost
- **NPS drifted from 8.1 to 6.4 over 6 months** (-20.4%), with ARIMA forecasting continued erosion; the model fired alerts on 3 of 5 monitored KPIs
- **poor_service theme in Southwest branch carries the most negative LLM-scored sentiment at -1.000** — combined with priority_score 56.77, it ranks 6th on the global hotspot table and warrants immediate attention

---

## Architecture

```
Phase 1 — Synthetic Data Generation
  generate_synthetic_data.py
  --> data/raw/ (5 CSVs | 49,000 events | 10,000 customers | 15% friction)
         |
         v
Phase 2 — ETL Pipeline                        Airflow DAG (design)
  ingest.py --> clean_normalize.py --> load_duckdb.py
  --> data/atlas.duckdb
      analytics.customer_event_log (49,000 rows)
         |
         v
Phase 3 — Journey Intelligence
  journey_stitcher.py  --> analytics.customer_journeys (37,296 episodes)
  friction_detector.py --> analytics.friction_flags   (813 friction, 2.2%)
         |
         +-------------------------------+
         |                               |
         v                               v
Phase 4 — LLM Insight Engine     Phase 5 — KPI Monitor + Scoring
  groq_client.py                   kpi_aggregator.py
  theme_extractor.py               kpi_arima_monitor.py
  insight_aggregator.py            friction_scorer.py
  --> llm_insights (500 rows)      segment_query_builder.py
  --> llm_theme_summary (8 rows)   alert_dispatcher.py
                                   --> kpi_alerts (3 alerts fired)
                                   --> friction_hotspots (75 segments)
         |                               |
         +-------------------------------+
                       |
                       v
Phase 6 — Dashboard Export
  export_for_powerbi.py
  --> data/dashboard/ (6 CSVs | 37,920 total rows)
  --> Power BI Desktop (5 visuals)
```

---

## Tech Stack

| Tool | Purpose | Phase |
|------|---------|-------|
| Python 3.14 | All scripting | All |
| pandas 3.0 | ETL normalization, data manipulation | 1–6 |
| numpy 2.4 | Statistical operations, AR(1) noise generation | 1, 5 |
| faker 40 | Synthetic event and customer data generation | 1 |
| DuckDB 1.5 | Analytical database (local dev; replaces Snowflake) | 2–6 |
| python-dotenv | Secure credential loading from .env | All |
| scipy 1.17 | Chi-square stationarity test (friction distribution) | 3 |
| groq 1.4 + llama-3.1-8b-instant | LLM theme/sentiment extraction via Groq API | 4 |
| statsmodels 0.14 | ARIMA(2,d,2) forecasting + ADF stationarity test | 5 |
| Power BI Desktop | Interactive dashboard with 5 visuals | 6 |
| Apache Airflow | DAG orchestration design spec (@daily, retries=2) | 2 |
| Snowflake | Cloud DWH DDL design (DuckDB used locally) | 2 |

---

## Project Structure

```
ATLAS/
|-- .env                                  # credentials (gitignored)
|-- .gitignore
|-- README.md
|-- requirements.txt
|-- generate_synthetic_data.py            # Phase 1
|
|-- data/
|   |-- raw/                              # Phase 1 outputs (gitignored)
|   |   |-- call_center_logs.csv
|   |   |-- branch_visits.csv
|   |   |-- online_events.csv
|   |   |-- mobile_events.csv
|   |   `-- nps_surveys.csv
|   |-- processed/                        # Phase 3-5 outputs (gitignored)
|   |   |-- customer_journeys.csv
|   |   |-- friction_flags.csv
|   |   |-- llm_insights.csv
|   |   |-- llm_theme_summary.csv
|   |   |-- kpi_weekly_summary.csv
|   |   |-- friction_hotspots.csv
|   |   `-- atlas_alerts.log
|   |-- dashboard/                        # Phase 6 Power BI exports (gitignored)
|   |   |-- Friction Hotspots.csv
|   |   |-- KPI Weekly Trend.csv
|   |   |-- KPI Alerts.csv
|   |   |-- LLM Theme Summary.csv
|   |   |-- Customer Journeys.csv
|   |   |-- Segment Cuts.csv
|   |   `-- POWERBI_SETUP.md
|   `-- atlas.duckdb                      # DuckDB database (gitignored)
|
|-- sql/
|   `-- ddl/
|       `-- create_raw_tables.sql         # Snowflake DDL (design reference)
|
`-- src/
    |-- 02_etl_pipeline/
    |   |-- ingest.py
    |   |-- clean_normalize.py
    |   |-- load_duckdb.py
    |   `-- atlas_dag.py                  # Airflow DAG
    |-- 03_journey_stitcher/
    |   `-- journey_stitcher.py
    |-- 04_friction_detector/
    |   `-- friction_detector.py
    |-- 05_llm_insight_engine/
    |   |-- groq_client.py
    |   |-- theme_extractor.py
    |   `-- insight_aggregator.py
    |-- 06_kpi_monitor/
    |   |-- kpi_aggregator.py
    |   `-- kpi_arima_monitor.py
    |-- 07_friction_scoring/
    |   `-- friction_scorer.py
    |-- 08_segment_optimizer/
    |   `-- segment_query_builder.py
    |-- 09_alerting/
    |   `-- alert_dispatcher.py
    `-- 10_dashboard/
        `-- export_for_powerbi.py
```

---

## Setup & Run

### 1. Clone and install

```bash
git clone https://github.com/MunagalaDhanush/ATLAS.git
cd ATLAS
pip install -r requirements.txt
```

### 2. Configure credentials

Create a `.env` file in the project root:

```
DB_ENGINE=duckdb
DB_PATH=data/atlas.duckdb
GROQ_API_KEY=your_groq_api_key_here
```

Get a free Groq API key at console.groq.com. The free tier supports 30 req/min (sufficient for Phase 4).

### 3. Run all phases in order

```bash
# Phase 1 — Generate synthetic data
python generate_synthetic_data.py

# Phase 2 — Load into DuckDB
python src/02_etl_pipeline/load_duckdb.py

# Phase 3 — Journey stitching and friction detection
python src/03_journey_stitcher/journey_stitcher.py
python src/04_friction_detector/friction_detector.py

# Phase 4 — LLM insight extraction (~30 min, free tier rate limits)
python src/05_llm_insight_engine/theme_extractor.py
python src/05_llm_insight_engine/insight_aggregator.py

# Phase 5 — KPI monitoring and friction scoring
python src/06_kpi_monitor/kpi_aggregator.py
python src/06_kpi_monitor/kpi_arima_monitor.py
python src/07_friction_scoring/friction_scorer.py
python src/08_segment_optimizer/segment_query_builder.py
python src/09_alerting/alert_dispatcher.py

# Phase 6 — Export for Power BI
python src/10_dashboard/export_for_powerbi.py
```

---

## Module Descriptions

| Module | Script | What It Does | Output |
|--------|--------|--------------|--------|
| Synthetic Data | `generate_synthetic_data.py` | Generates 49,000 events across 5 channels; bakes in 15% friction population, 40% cross-channel same-product, skewed NPS | 5 CSVs in `data/raw/` |
| Ingest | `ingest.py` | Validates schema, parses timestamps and booleans for all 5 source files | Dict of DataFrames |
| Normalize | `clean_normalize.py` | Maps 5 schemas to unified `CUSTOMER_EVENT_LOG`; detects initial friction candidates | Unified 49,000-row DataFrame |
| Load DuckDB | `load_duckdb.py` | Truncate-and-reload pattern into DuckDB; verify() prints post-load row counts | `analytics.customer_event_log` |
| Journey Stitcher | `journey_stitcher.py` | 72h gap-based episode windowing; vectorized with pandas shift+cumsum | `customer_journeys` (37,296 rows) |
| Friction Detector | `friction_detector.py` | 4-rule friction scoring; chi-square product test; friction rates by region and sequence | `friction_flags` (37,296 rows) |
| Groq Client | `groq_client.py` | Lazy-initialized Groq API wrapper; exponential backoff on 429; JSON parse+validate | Insight dict per call |
| Theme Extractor | `theme_extractor.py` | Samples 500 text-bearing events; batches of 25 with 2s sleep; 0% failure rate | `llm_insights` (500 rows) |
| Insight Aggregator | `insight_aggregator.py` | Aggregates LLM output by theme, channel, urgency; friction vs non-friction comparison | `llm_theme_summary` (8 rows) |
| KPI Aggregator | `kpi_aggregator.py` | 28 weeks of 5 KPIs from DuckDB; overlays AR(1) noise + trend for ARIMA viability | `kpi_weekly_summary` (28 rows) |
| ARIMA Monitor | `kpi_arima_monitor.py` | ADF stationarity test per KPI; ARIMA(2,d,2) fit; 10% alert threshold | `kpi_alerts` (5 rows, 3 fired) |
| Friction Scorer | `friction_scorer.py` | Groups 813 friction episodes by product+region+channel; composite priority_score formula | `friction_hotspots` (75 rows) |
| Segment Builder | `segment_query_builder.py` | Parameterized query function with input validation; joins journeys with LLM insights | DataFrame on demand |
| Alert Dispatcher | `alert_dispatcher.py` | Formats and prints alerts; appends to `atlas_alerts.log` | `data/processed/atlas_alerts.log` |
| PBI Exporter | `export_for_powerbi.py` | Exports 6 clean CSVs with Power BI-friendly column names | `data/dashboard/` |

---

## Skills Demonstrated

| Skill | Where Demonstrated | ATLAS Evidence |
|-------|--------------------|----------------|
| Python data engineering | Phases 1–2 | 5-source ETL with schema validation, type coercion, and DuckDB load |
| SQL / analytical query design | Phases 2–5 | 15+ DuckDB queries: CTEs, window functions, QUALIFY, lateral joins |
| Statistical hypothesis testing | Phase 3 | Chi-square test on friction episode distribution across products (scipy) |
| Time-series forecasting | Phase 5 | ADF stationarity test + ARIMA(2,d,2) on 5 KPI series; 3 alerts fired |
| NLP / LLM API integration | Phase 4 | Groq API with structured JSON output, retry/backoff, 500-row extraction at 0% fail |
| Segmentation and scoring | Phases 3, 5 | 4-rule friction engine; composite 100-point priority_score for 75 hotspot segments |
| Pipeline design and orchestration | Phase 2 | Apache Airflow DAG (PythonOperator, retries=2, @daily schedule) |
| Cloud data warehouse design | Phase 2 | Snowflake DDL with TIMESTAMP_NTZ, BOOLEAN, VARCHAR(n); DuckDB for local dev |
| Data visualization / dashboarding | Phase 6 | Power BI: 5 visuals, dual-axis line chart, conditional formatting, color theme |
| Parameterized reporting | Phase 5 | `build_and_run_segment()` with dynamic WHERE clause and input validation |
| Secure credential management | All | python-dotenv pattern; zero hardcoded keys across all 15 scripts |
| Technical communication | README, POWERBI_SETUP.md | End-to-end documentation from architecture to visual-level Power BI instructions |

---

## Results Summary

### ARIMA KPI Alerts (3/5 KPIs fired)

| KPI | Current | Forecast | Change | Alert |
|-----|---------|----------|--------|-------|
| weekly_friction_rate | 0.0093 | 0.0200 | +114.8% | FIRED — deteriorating |
| weekly_channel_escalation_rate | 0.0053 | 0.0433 | +716.1% | FIRED — deteriorating |
| weekly_resolution_rate | 0.4265 | 0.6410 | +50.3% | FIRED — improving |
| weekly_avg_nps | 6.3500 | 6.4890 | +2.2% | clear |
| weekly_avg_episode_duration | 34.57 hrs | 35.06 hrs | +1.4% | clear |

*Friction rate and escalation rate alerts reflect ARIMA mean-reversion from a partial final week (June 15); resolution rate improvement alert is genuine.*

### Top 5 Friction Hotspots

| Rank | Product | Region | Channel | Unresolved Rate | Priority Score |
|------|---------|--------|---------|-----------------|----------------|
| 1 | checking | Southwest | mobile | 100.0% | 64.47 |
| 2 | savings | Northeast | call | 80.0% | 60.19 |
| 3 | savings | Southeast | mobile | 60.0% | 59.90 |
| 4 | checking | Southwest | call | 88.9% | 58.88 |
| 5 | credit_card | Northeast | call | 55.6% | 56.90 |

### LLM Theme Breakdown (top 4 of 8 themes, n=500)

| Theme | Count | Avg Sentiment | % Unresolved |
|-------|-------|--------------|--------------|
| balance_inquiry | 185 (37.0%) | +0.621 | 13.0% |
| app_issue | 86 (17.2%) | -0.814 | 100.0% |
| payment_failed | 72 (14.4%) | -0.686 | 86.1% |
| fraud_dispute | 64 (12.8%) | -0.223 | 48.4% |

---

## Dashboard Preview

*[Add Power BI screenshot after building the dashboard — see `data/dashboard/POWERBI_SETUP.md` for build instructions]*

---

## Author

**Dhanush Munagala** | MS MIS, University of Houston | [munagaladhanush.github.io](https://munagaladhanush.github.io)
