-- ATLAS Phase 2 — Snowflake DDL
-- Run once to bootstrap ATLAS_DB.RAW (source tables) and ATLAS_DB.ANALYTICS (unified table).
-- Assumes ATLAS_DB database already exists and the executing role has CREATE SCHEMA / CREATE TABLE.

USE DATABASE ATLAS_DB;

-- ── RAW Schema ─────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS RAW;

CREATE OR REPLACE TABLE ATLAS_DB.RAW.CALL_CENTER_LOGS (
    customer_id          VARCHAR(36)   NOT NULL,
    call_id              VARCHAR(36)   NOT NULL,
    call_timestamp       TIMESTAMP_NTZ NOT NULL,
    call_duration_sec    INT,
    ivr_resolution       BOOLEAN,
    agent_resolution     BOOLEAN,
    product_involved     VARCHAR(50),
    issue_category       VARCHAR(50),
    transcript_text      TEXT,
    region               VARCHAR(50),
    PRIMARY KEY (call_id)
);

CREATE OR REPLACE TABLE ATLAS_DB.RAW.BRANCH_VISITS (
    customer_id      VARCHAR(36)   NOT NULL,
    visit_id         VARCHAR(36)   NOT NULL,
    visit_timestamp  TIMESTAMP_NTZ NOT NULL,
    branch_id        VARCHAR(20),
    visit_purpose    VARCHAR(50),
    product_involved VARCHAR(50),
    resolved_flag    BOOLEAN,
    banker_notes     TEXT,
    region           VARCHAR(50),
    PRIMARY KEY (visit_id)
);

CREATE OR REPLACE TABLE ATLAS_DB.RAW.ONLINE_EVENTS (
    customer_id      VARCHAR(36)   NOT NULL,
    session_id       VARCHAR(36)   NOT NULL,
    event_timestamp  TIMESTAMP_NTZ NOT NULL,
    event_type       VARCHAR(50),
    page_name        VARCHAR(100),
    product_involved VARCHAR(50),
    session_resolved BOOLEAN,
    region           VARCHAR(50),
    PRIMARY KEY (session_id)
);

CREATE OR REPLACE TABLE ATLAS_DB.RAW.MOBILE_EVENTS (
    customer_id      VARCHAR(36)   NOT NULL,
    event_id         VARCHAR(36)   NOT NULL,
    event_timestamp  TIMESTAMP_NTZ NOT NULL,
    event_type       VARCHAR(50),
    feature_name     VARCHAR(100),
    product_involved VARCHAR(50),
    feedback_text    TEXT,
    resolved_flag    BOOLEAN,
    region           VARCHAR(50),
    PRIMARY KEY (event_id)
);

CREATE OR REPLACE TABLE ATLAS_DB.RAW.NPS_SURVEYS (
    customer_id             VARCHAR(36)   NOT NULL,
    survey_id               VARCHAR(36)   NOT NULL,
    survey_timestamp        TIMESTAMP_NTZ NOT NULL,
    nps_score               INT,
    csat_score              INT,
    open_response           TEXT,
    product_involved        VARCHAR(50),
    channel_of_last_contact VARCHAR(50),
    region                  VARCHAR(50),
    PRIMARY KEY (survey_id)
);

-- ── ANALYTICS Schema ───────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS ANALYTICS;

CREATE OR REPLACE TABLE ATLAS_DB.ANALYTICS.CUSTOMER_EVENT_LOG (
    event_id              VARCHAR(36)   NOT NULL,
    customer_id           VARCHAR(36)   NOT NULL,
    channel               VARCHAR(20)   NOT NULL,
    event_timestamp       TIMESTAMP_NTZ NOT NULL,
    product_involved      VARCHAR(50),
    issue_category        VARCHAR(50),
    resolved_flag         BOOLEAN,
    text_content          TEXT,
    region                VARCHAR(50),
    is_friction_candidate BOOLEAN       DEFAULT FALSE,
    load_timestamp        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (event_id)
);
