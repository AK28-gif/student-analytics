-- =====================================================================
-- Student Performance & Dropout-Risk Warehouse (PostgreSQL)
-- Source: UCI Student Performance dataset (Mathematics + Portuguese files)
-- Layers:  raw files on disk (data/raw/<run_id>/)
--          staging   - rows exactly as landed (TEXT) + lineage columns
--          clean     - typed, validated, de-duplicated, standardised ids
--          analytics - star schema (dims + facts) + data marts
--          ml        - Part 2: batch predictions + monitoring reports
--          audit     - pipeline runs, ingestion log, rejected records, DQ results
-- Idempotent: safe to run repeatedly.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS clean;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS ml;

-- ---------------------------------------------------------------------
-- AUDIT
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit.pipeline_runs (
    run_id        TEXT PRIMARY KEY,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    status        TEXT NOT NULL DEFAULT 'RUNNING',   -- RUNNING / SUCCESS / FAILED
    triggered_by  TEXT,                              -- cli / airflow / dvc
    message       TEXT
);

CREATE TABLE IF NOT EXISTS audit.ingestion_log (
    id               BIGSERIAL PRIMARY KEY,
    run_id           TEXT NOT NULL,
    source_name      TEXT NOT NULL,
    source_type      TEXT NOT NULL,      -- http_zip
    source_location  TEXT NOT NULL,
    extracted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    status           TEXT NOT NULL,      -- SUCCESS / FAILED
    row_count        INTEGER,
    failed_row_count INTEGER DEFAULT 0,
    raw_path         TEXT,
    checksum_sha256  TEXT,
    error_message    TEXT
);

CREATE TABLE IF NOT EXISTS audit.rejected_records (
    id           BIGSERIAL PRIMARY KEY,
    run_id       TEXT NOT NULL,
    stage        TEXT NOT NULL,          -- ingestion / cleaning
    source_name  TEXT NOT NULL,
    rule_name    TEXT NOT NULL,
    record_key   TEXT,
    reason       TEXT NOT NULL,
    record       JSONB,
    logged_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_rejected_run ON audit.rejected_records(run_id);

CREATE TABLE IF NOT EXISTS audit.dq_results (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL,
    check_name      TEXT NOT NULL,
    table_name      TEXT NOT NULL,
    severity        TEXT NOT NULL,       -- critical / warning
    passed          BOOLEAN NOT NULL,
    observed_value  NUMERIC,
    expectation     TEXT,
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- STAGING  (stored as landed: TEXT + lineage columns)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.stg_uci_student (
    source_file TEXT, source_row INTEGER, subject_code TEXT,
    school TEXT, sex TEXT, age TEXT, address TEXT, famsize TEXT, pstatus TEXT,
    medu TEXT, fedu TEXT, mjob TEXT, fjob TEXT, reason TEXT, guardian TEXT,
    traveltime TEXT, studytime TEXT, failures TEXT, schoolsup TEXT, famsup TEXT,
    paid TEXT, activities TEXT, nursery TEXT, higher TEXT, internet TEXT,
    romantic TEXT, famrel TEXT, freetime TEXT, goout TEXT, dalc TEXT, walc TEXT,
    health TEXT, absences TEXT, g1 TEXT, g2 TEXT, g3 TEXT,
    _run_id TEXT, _loaded_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------
-- CLEAN  (typed, validated, standardised identifiers, de-duplicated)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clean.student (
    student_id TEXT PRIMARY KEY,           -- canonical id STU00001
    match_key  TEXT NOT NULL,
    school TEXT, sex TEXT, age SMALLINT, address TEXT, famsize TEXT, pstatus TEXT,
    medu SMALLINT, fedu SMALLINT, mjob TEXT, fjob TEXT, reason TEXT, guardian TEXT,
    traveltime SMALLINT, nursery BOOLEAN, internet BOOLEAN, higher BOOLEAN, romantic BOOLEAN,
    famrel SMALLINT, freetime SMALLINT, goout SMALLINT, dalc SMALLINT, walc SMALLINT,
    health SMALLINT
);

CREATE TABLE IF NOT EXISTS clean.enrollment (
    student_id TEXT REFERENCES clean.student(student_id),
    subject_code TEXT,
    studytime SMALLINT, failures SMALLINT, schoolsup BOOLEAN, famsup BOOLEAN,
    paid BOOLEAN, activities BOOLEAN,
    absences SMALLINT, absences_imputed BOOLEAN NOT NULL DEFAULT FALSE,
    g1 SMALLINT, g2 SMALLINT, g3 SMALLINT,
    PRIMARY KEY (student_id, subject_code)
);

-- ---------------------------------------------------------------------
-- ANALYTICS  (star schema + marts)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.dim_student (
    student_key SERIAL PRIMARY KEY,
    student_id TEXT UNIQUE NOT NULL,
    school TEXT, school_name TEXT, sex TEXT, age SMALLINT, address_type TEXT,
    family_size TEXT, parent_status TEXT, mother_education SMALLINT, father_education SMALLINT,
    mother_job TEXT, father_job TEXT, guardian TEXT, internet_access BOOLEAN,
    wants_higher_education BOOLEAN, travel_time SMALLINT, health SMALLINT
);

CREATE TABLE IF NOT EXISTS analytics.dim_subject (
    subject_key SERIAL PRIMARY KEY,
    subject_code TEXT UNIQUE NOT NULL, subject_name TEXT, department TEXT
);

CREATE TABLE IF NOT EXISTS analytics.dim_term (
    term_key SERIAL PRIMARY KEY,
    term_code TEXT UNIQUE NOT NULL, term_name TEXT, term_order SMALLINT
);

-- Grain: student x subject x assessment term (G1 / G2 / G3)
CREATE TABLE IF NOT EXISTS analytics.fact_student_term (
    student_key INT REFERENCES analytics.dim_student(student_key),
    subject_key INT REFERENCES analytics.dim_subject(subject_key),
    term_key    INT REFERENCES analytics.dim_term(term_key),
    grade SMALLINT, passed BOOLEAN, prev_term_grade SMALLINT, grade_change SMALLINT,
    PRIMARY KEY (student_key, subject_key, term_key)
);

-- Grain: student x subject (one enrolment)
CREATE TABLE IF NOT EXISTS analytics.fact_enrollment (
    student_key INT REFERENCES analytics.dim_student(student_key),
    subject_key INT REFERENCES analytics.dim_subject(subject_key),
    study_time SMALLINT, prior_failures SMALLINT, school_support BOOLEAN,
    family_support BOOLEAN, paid_classes BOOLEAN, extra_activities BOOLEAN,
    absences SMALLINT, attendance_pct NUMERIC(5,2), avg_internal_marks NUMERIC(5,2),
    final_grade SMALLINT, passed BOOLEAN,
    PRIMARY KEY (student_key, subject_key)
);

-- Data mart: one row per student x subject (denormalised). Feeds dashboard + ML features.
CREATE TABLE IF NOT EXISTS analytics.mart_student_subject (
    student_id TEXT, subject_code TEXT, subject_name TEXT, department TEXT,
    school TEXT, school_name TEXT, sex TEXT, age SMALLINT, address_type TEXT, family_size TEXT,
    parent_status TEXT, mother_education SMALLINT, father_education SMALLINT,
    mother_job TEXT, father_job TEXT, reason TEXT, guardian TEXT,
    internet_access BOOLEAN, wants_higher_education BOOLEAN, attended_nursery BOOLEAN,
    travel_time SMALLINT, study_time SMALLINT, prior_failures SMALLINT,
    school_support BOOLEAN, family_support BOOLEAN, paid_classes BOOLEAN,
    extra_activities BOOLEAN, romantic BOOLEAN, family_relationship SMALLINT,
    free_time SMALLINT, going_out SMALLINT, weekday_alcohol SMALLINT,
    weekend_alcohol SMALLINT, health SMALLINT,
    absences SMALLINT, attendance_pct NUMERIC(5,2), absences_imputed BOOLEAN,
    grade_p1 SMALLINT, grade_p2 SMALLINT, final_grade SMALLINT,
    avg_internal_marks NUMERIC(5,2), prev_semester_grade SMALLINT, grade_trend SMALLINT,
    pass_status TEXT, risk_score SMALLINT, risk_level TEXT, risk_reasons TEXT,
    PRIMARY KEY (student_id, subject_code)
);

CREATE TABLE IF NOT EXISTS analytics.mart_subject_term_summary (
    subject_code TEXT, subject_name TEXT, department TEXT, school TEXT,
    term_code TEXT, term_name TEXT, term_order SMALLINT,
    students INT, avg_grade NUMERIC(5,2), pass_rate_pct NUMERIC(5,2),
    fail_count INT, avg_attendance_pct NUMERIC(5,2)
);

CREATE TABLE IF NOT EXISTS analytics.mart_student_overview (
    student_id TEXT PRIMARY KEY, school TEXT, sex TEXT, age SMALLINT,
    subjects_enrolled SMALLINT, subjects_failed SMALLINT, avg_final_grade NUMERIC(5,2),
    avg_internal_marks NUMERIC(5,2), overall_attendance_pct NUMERIC(5,2),
    highest_risk_level TEXT, max_risk_score SMALLINT
);

-- ---------------------------------------------------------------------
-- ML (Part 2)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ml.risk_predictions (
    id BIGSERIAL PRIMARY KEY,
    scored_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_name TEXT, model_version TEXT, model_type TEXT,
    student_id TEXT, subject_code TEXT,
    fail_probability NUMERIC(6,4), predicted_fail BOOLEAN, risk_band TEXT,
    actual_fail BOOLEAN
);

CREATE TABLE IF NOT EXISTS ml.monitoring_reports (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_version TEXT, dataset TEXT,
    drift_share NUMERIC(5,3), drifted_features TEXT,
    reference_positive_rate NUMERIC(5,3), current_positive_rate NUMERIC(5,3),
    reference_f1 NUMERIC(5,3), current_f1 NUMERIC(5,3),
    api_requests INT, api_error_rate NUMERIC(5,3), api_p95_latency_ms NUMERIC(10,2),
    retrain_recommended BOOLEAN, reasons TEXT, report JSONB
);
