--
-- PostgreSQL database dump
--

\restrict LADjrFzXGAoTbx1mJYrni81NG8GdU4WWDFbI2VN8uNkhyyQzv0dU7nHe1oxsfnb

-- Dumped from database version 16.15 (Homebrew)
-- Dumped by pg_dump version 16.15 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: analytics; Type: SCHEMA; Schema: -; Owner: student_app
--

CREATE SCHEMA analytics;


ALTER SCHEMA analytics OWNER TO student_app;

--
-- Name: audit; Type: SCHEMA; Schema: -; Owner: student_app
--

CREATE SCHEMA audit;


ALTER SCHEMA audit OWNER TO student_app;

--
-- Name: clean; Type: SCHEMA; Schema: -; Owner: student_app
--

CREATE SCHEMA clean;


ALTER SCHEMA clean OWNER TO student_app;

--
-- Name: ml; Type: SCHEMA; Schema: -; Owner: student_app
--

CREATE SCHEMA ml;


ALTER SCHEMA ml OWNER TO student_app;

--
-- Name: staging; Type: SCHEMA; Schema: -; Owner: student_app
--

CREATE SCHEMA staging;


ALTER SCHEMA staging OWNER TO student_app;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: dim_student; Type: TABLE; Schema: analytics; Owner: student_app
--

CREATE TABLE analytics.dim_student (
    student_key integer NOT NULL,
    student_id text NOT NULL,
    school text,
    school_name text,
    sex text,
    age smallint,
    address_type text,
    family_size text,
    parent_status text,
    mother_education smallint,
    father_education smallint,
    mother_job text,
    father_job text,
    guardian text,
    internet_access boolean,
    wants_higher_education boolean,
    travel_time smallint,
    health smallint
);


ALTER TABLE analytics.dim_student OWNER TO student_app;

--
-- Name: dim_student_student_key_seq; Type: SEQUENCE; Schema: analytics; Owner: student_app
--

CREATE SEQUENCE analytics.dim_student_student_key_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE analytics.dim_student_student_key_seq OWNER TO student_app;

--
-- Name: dim_student_student_key_seq; Type: SEQUENCE OWNED BY; Schema: analytics; Owner: student_app
--

ALTER SEQUENCE analytics.dim_student_student_key_seq OWNED BY analytics.dim_student.student_key;


--
-- Name: dim_subject; Type: TABLE; Schema: analytics; Owner: student_app
--

CREATE TABLE analytics.dim_subject (
    subject_key integer NOT NULL,
    subject_code text NOT NULL,
    subject_name text,
    department text
);


ALTER TABLE analytics.dim_subject OWNER TO student_app;

--
-- Name: dim_subject_subject_key_seq; Type: SEQUENCE; Schema: analytics; Owner: student_app
--

CREATE SEQUENCE analytics.dim_subject_subject_key_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE analytics.dim_subject_subject_key_seq OWNER TO student_app;

--
-- Name: dim_subject_subject_key_seq; Type: SEQUENCE OWNED BY; Schema: analytics; Owner: student_app
--

ALTER SEQUENCE analytics.dim_subject_subject_key_seq OWNED BY analytics.dim_subject.subject_key;


--
-- Name: dim_term; Type: TABLE; Schema: analytics; Owner: student_app
--

CREATE TABLE analytics.dim_term (
    term_key integer NOT NULL,
    term_code text NOT NULL,
    term_name text,
    term_order smallint
);


ALTER TABLE analytics.dim_term OWNER TO student_app;

--
-- Name: dim_term_term_key_seq; Type: SEQUENCE; Schema: analytics; Owner: student_app
--

CREATE SEQUENCE analytics.dim_term_term_key_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE analytics.dim_term_term_key_seq OWNER TO student_app;

--
-- Name: dim_term_term_key_seq; Type: SEQUENCE OWNED BY; Schema: analytics; Owner: student_app
--

ALTER SEQUENCE analytics.dim_term_term_key_seq OWNED BY analytics.dim_term.term_key;


--
-- Name: fact_enrollment; Type: TABLE; Schema: analytics; Owner: student_app
--

CREATE TABLE analytics.fact_enrollment (
    student_key integer NOT NULL,
    subject_key integer NOT NULL,
    study_time smallint,
    prior_failures smallint,
    school_support boolean,
    family_support boolean,
    paid_classes boolean,
    extra_activities boolean,
    absences smallint,
    attendance_pct numeric(5,2),
    avg_internal_marks numeric(5,2),
    final_grade smallint,
    passed boolean
);


ALTER TABLE analytics.fact_enrollment OWNER TO student_app;

--
-- Name: fact_student_term; Type: TABLE; Schema: analytics; Owner: student_app
--

CREATE TABLE analytics.fact_student_term (
    student_key integer NOT NULL,
    subject_key integer NOT NULL,
    term_key integer NOT NULL,
    grade smallint,
    passed boolean,
    prev_term_grade smallint,
    grade_change smallint
);


ALTER TABLE analytics.fact_student_term OWNER TO student_app;

--
-- Name: mart_student_overview; Type: TABLE; Schema: analytics; Owner: student_app
--

CREATE TABLE analytics.mart_student_overview (
    student_id text NOT NULL,
    school text,
    sex text,
    age smallint,
    subjects_enrolled smallint,
    subjects_failed smallint,
    avg_final_grade numeric(5,2),
    avg_internal_marks numeric(5,2),
    overall_attendance_pct numeric(5,2),
    highest_risk_level text,
    max_risk_score smallint
);


ALTER TABLE analytics.mart_student_overview OWNER TO student_app;

--
-- Name: mart_student_subject; Type: TABLE; Schema: analytics; Owner: student_app
--

CREATE TABLE analytics.mart_student_subject (
    student_id text NOT NULL,
    subject_code text NOT NULL,
    subject_name text,
    department text,
    school text,
    school_name text,
    sex text,
    age smallint,
    address_type text,
    family_size text,
    parent_status text,
    mother_education smallint,
    father_education smallint,
    mother_job text,
    father_job text,
    reason text,
    guardian text,
    internet_access boolean,
    wants_higher_education boolean,
    attended_nursery boolean,
    travel_time smallint,
    study_time smallint,
    prior_failures smallint,
    school_support boolean,
    family_support boolean,
    paid_classes boolean,
    extra_activities boolean,
    romantic boolean,
    family_relationship smallint,
    free_time smallint,
    going_out smallint,
    weekday_alcohol smallint,
    weekend_alcohol smallint,
    health smallint,
    absences smallint,
    attendance_pct numeric(5,2),
    absences_imputed boolean,
    grade_p1 smallint,
    grade_p2 smallint,
    final_grade smallint,
    avg_internal_marks numeric(5,2),
    prev_semester_grade smallint,
    grade_trend smallint,
    pass_status text,
    risk_score smallint,
    risk_level text,
    risk_reasons text
);


ALTER TABLE analytics.mart_student_subject OWNER TO student_app;

--
-- Name: mart_subject_term_summary; Type: TABLE; Schema: analytics; Owner: student_app
--

CREATE TABLE analytics.mart_subject_term_summary (
    subject_code text,
    subject_name text,
    department text,
    school text,
    term_code text,
    term_name text,
    term_order smallint,
    students integer,
    avg_grade numeric(5,2),
    pass_rate_pct numeric(5,2),
    fail_count integer,
    avg_attendance_pct numeric(5,2)
);


ALTER TABLE analytics.mart_subject_term_summary OWNER TO student_app;

--
-- Name: dq_results; Type: TABLE; Schema: audit; Owner: student_app
--

CREATE TABLE audit.dq_results (
    id bigint NOT NULL,
    run_id text NOT NULL,
    check_name text NOT NULL,
    table_name text NOT NULL,
    severity text NOT NULL,
    passed boolean NOT NULL,
    observed_value numeric,
    expectation text,
    checked_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE audit.dq_results OWNER TO student_app;

--
-- Name: dq_results_id_seq; Type: SEQUENCE; Schema: audit; Owner: student_app
--

CREATE SEQUENCE audit.dq_results_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE audit.dq_results_id_seq OWNER TO student_app;

--
-- Name: dq_results_id_seq; Type: SEQUENCE OWNED BY; Schema: audit; Owner: student_app
--

ALTER SEQUENCE audit.dq_results_id_seq OWNED BY audit.dq_results.id;


--
-- Name: ingestion_log; Type: TABLE; Schema: audit; Owner: student_app
--

CREATE TABLE audit.ingestion_log (
    id bigint NOT NULL,
    run_id text NOT NULL,
    source_name text NOT NULL,
    source_type text NOT NULL,
    source_location text NOT NULL,
    extracted_at timestamp with time zone DEFAULT now() NOT NULL,
    status text NOT NULL,
    row_count integer,
    failed_row_count integer DEFAULT 0,
    raw_path text,
    checksum_sha256 text,
    error_message text
);


ALTER TABLE audit.ingestion_log OWNER TO student_app;

--
-- Name: ingestion_log_id_seq; Type: SEQUENCE; Schema: audit; Owner: student_app
--

CREATE SEQUENCE audit.ingestion_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE audit.ingestion_log_id_seq OWNER TO student_app;

--
-- Name: ingestion_log_id_seq; Type: SEQUENCE OWNED BY; Schema: audit; Owner: student_app
--

ALTER SEQUENCE audit.ingestion_log_id_seq OWNED BY audit.ingestion_log.id;


--
-- Name: pipeline_runs; Type: TABLE; Schema: audit; Owner: student_app
--

CREATE TABLE audit.pipeline_runs (
    run_id text NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    status text DEFAULT 'RUNNING'::text NOT NULL,
    triggered_by text,
    message text
);


ALTER TABLE audit.pipeline_runs OWNER TO student_app;

--
-- Name: rejected_records; Type: TABLE; Schema: audit; Owner: student_app
--

CREATE TABLE audit.rejected_records (
    id bigint NOT NULL,
    run_id text NOT NULL,
    stage text NOT NULL,
    source_name text NOT NULL,
    rule_name text NOT NULL,
    record_key text,
    reason text NOT NULL,
    record jsonb,
    logged_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE audit.rejected_records OWNER TO student_app;

--
-- Name: rejected_records_id_seq; Type: SEQUENCE; Schema: audit; Owner: student_app
--

CREATE SEQUENCE audit.rejected_records_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE audit.rejected_records_id_seq OWNER TO student_app;

--
-- Name: rejected_records_id_seq; Type: SEQUENCE OWNED BY; Schema: audit; Owner: student_app
--

ALTER SEQUENCE audit.rejected_records_id_seq OWNED BY audit.rejected_records.id;


--
-- Name: enrollment; Type: TABLE; Schema: clean; Owner: student_app
--

CREATE TABLE clean.enrollment (
    student_id text NOT NULL,
    subject_code text NOT NULL,
    studytime smallint,
    failures smallint,
    schoolsup boolean,
    famsup boolean,
    paid boolean,
    activities boolean,
    absences smallint,
    absences_imputed boolean DEFAULT false NOT NULL,
    g1 smallint,
    g2 smallint,
    g3 smallint
);


ALTER TABLE clean.enrollment OWNER TO student_app;

--
-- Name: student; Type: TABLE; Schema: clean; Owner: student_app
--

CREATE TABLE clean.student (
    student_id text NOT NULL,
    match_key text NOT NULL,
    school text,
    sex text,
    age smallint,
    address text,
    famsize text,
    pstatus text,
    medu smallint,
    fedu smallint,
    mjob text,
    fjob text,
    reason text,
    guardian text,
    traveltime smallint,
    nursery boolean,
    internet boolean,
    higher boolean,
    romantic boolean,
    famrel smallint,
    freetime smallint,
    goout smallint,
    dalc smallint,
    walc smallint,
    health smallint
);


ALTER TABLE clean.student OWNER TO student_app;

--
-- Name: monitoring_reports; Type: TABLE; Schema: ml; Owner: student_app
--

CREATE TABLE ml.monitoring_reports (
    id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    model_version text,
    dataset text,
    drift_share numeric(5,3),
    drifted_features text,
    reference_positive_rate numeric(5,3),
    current_positive_rate numeric(5,3),
    reference_f1 numeric(5,3),
    current_f1 numeric(5,3),
    api_requests integer,
    api_error_rate numeric(5,3),
    api_p95_latency_ms numeric(10,2),
    retrain_recommended boolean,
    reasons text,
    report jsonb
);


ALTER TABLE ml.monitoring_reports OWNER TO student_app;

--
-- Name: monitoring_reports_id_seq; Type: SEQUENCE; Schema: ml; Owner: student_app
--

CREATE SEQUENCE ml.monitoring_reports_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE ml.monitoring_reports_id_seq OWNER TO student_app;

--
-- Name: monitoring_reports_id_seq; Type: SEQUENCE OWNED BY; Schema: ml; Owner: student_app
--

ALTER SEQUENCE ml.monitoring_reports_id_seq OWNED BY ml.monitoring_reports.id;


--
-- Name: risk_predictions; Type: TABLE; Schema: ml; Owner: student_app
--

CREATE TABLE ml.risk_predictions (
    id bigint NOT NULL,
    scored_at timestamp with time zone DEFAULT now() NOT NULL,
    model_name text,
    model_version text,
    model_type text,
    student_id text,
    subject_code text,
    fail_probability numeric(6,4),
    predicted_fail boolean,
    risk_band text,
    actual_fail boolean
);


ALTER TABLE ml.risk_predictions OWNER TO student_app;

--
-- Name: risk_predictions_id_seq; Type: SEQUENCE; Schema: ml; Owner: student_app
--

CREATE SEQUENCE ml.risk_predictions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE ml.risk_predictions_id_seq OWNER TO student_app;

--
-- Name: risk_predictions_id_seq; Type: SEQUENCE OWNED BY; Schema: ml; Owner: student_app
--

ALTER SEQUENCE ml.risk_predictions_id_seq OWNED BY ml.risk_predictions.id;


--
-- Name: stg_uci_student; Type: TABLE; Schema: staging; Owner: student_app
--

CREATE TABLE staging.stg_uci_student (
    source_file text,
    source_row integer,
    subject_code text,
    school text,
    sex text,
    age text,
    address text,
    famsize text,
    pstatus text,
    medu text,
    fedu text,
    mjob text,
    fjob text,
    reason text,
    guardian text,
    traveltime text,
    studytime text,
    failures text,
    schoolsup text,
    famsup text,
    paid text,
    activities text,
    nursery text,
    higher text,
    internet text,
    romantic text,
    famrel text,
    freetime text,
    goout text,
    dalc text,
    walc text,
    health text,
    absences text,
    g1 text,
    g2 text,
    g3 text,
    _run_id text,
    _loaded_at timestamp with time zone DEFAULT now()
);


ALTER TABLE staging.stg_uci_student OWNER TO student_app;

--
-- Name: dim_student student_key; Type: DEFAULT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.dim_student ALTER COLUMN student_key SET DEFAULT nextval('analytics.dim_student_student_key_seq'::regclass);


--
-- Name: dim_subject subject_key; Type: DEFAULT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.dim_subject ALTER COLUMN subject_key SET DEFAULT nextval('analytics.dim_subject_subject_key_seq'::regclass);


--
-- Name: dim_term term_key; Type: DEFAULT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.dim_term ALTER COLUMN term_key SET DEFAULT nextval('analytics.dim_term_term_key_seq'::regclass);


--
-- Name: dq_results id; Type: DEFAULT; Schema: audit; Owner: student_app
--

ALTER TABLE ONLY audit.dq_results ALTER COLUMN id SET DEFAULT nextval('audit.dq_results_id_seq'::regclass);


--
-- Name: ingestion_log id; Type: DEFAULT; Schema: audit; Owner: student_app
--

ALTER TABLE ONLY audit.ingestion_log ALTER COLUMN id SET DEFAULT nextval('audit.ingestion_log_id_seq'::regclass);


--
-- Name: rejected_records id; Type: DEFAULT; Schema: audit; Owner: student_app
--

ALTER TABLE ONLY audit.rejected_records ALTER COLUMN id SET DEFAULT nextval('audit.rejected_records_id_seq'::regclass);


--
-- Name: monitoring_reports id; Type: DEFAULT; Schema: ml; Owner: student_app
--

ALTER TABLE ONLY ml.monitoring_reports ALTER COLUMN id SET DEFAULT nextval('ml.monitoring_reports_id_seq'::regclass);


--
-- Name: risk_predictions id; Type: DEFAULT; Schema: ml; Owner: student_app
--

ALTER TABLE ONLY ml.risk_predictions ALTER COLUMN id SET DEFAULT nextval('ml.risk_predictions_id_seq'::regclass);


--
-- Name: dim_student dim_student_pkey; Type: CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.dim_student
    ADD CONSTRAINT dim_student_pkey PRIMARY KEY (student_key);


--
-- Name: dim_student dim_student_student_id_key; Type: CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.dim_student
    ADD CONSTRAINT dim_student_student_id_key UNIQUE (student_id);


--
-- Name: dim_subject dim_subject_pkey; Type: CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.dim_subject
    ADD CONSTRAINT dim_subject_pkey PRIMARY KEY (subject_key);


--
-- Name: dim_subject dim_subject_subject_code_key; Type: CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.dim_subject
    ADD CONSTRAINT dim_subject_subject_code_key UNIQUE (subject_code);


--
-- Name: dim_term dim_term_pkey; Type: CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.dim_term
    ADD CONSTRAINT dim_term_pkey PRIMARY KEY (term_key);


--
-- Name: dim_term dim_term_term_code_key; Type: CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.dim_term
    ADD CONSTRAINT dim_term_term_code_key UNIQUE (term_code);


--
-- Name: fact_enrollment fact_enrollment_pkey; Type: CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.fact_enrollment
    ADD CONSTRAINT fact_enrollment_pkey PRIMARY KEY (student_key, subject_key);


--
-- Name: fact_student_term fact_student_term_pkey; Type: CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.fact_student_term
    ADD CONSTRAINT fact_student_term_pkey PRIMARY KEY (student_key, subject_key, term_key);


--
-- Name: mart_student_overview mart_student_overview_pkey; Type: CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.mart_student_overview
    ADD CONSTRAINT mart_student_overview_pkey PRIMARY KEY (student_id);


--
-- Name: mart_student_subject mart_student_subject_pkey; Type: CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.mart_student_subject
    ADD CONSTRAINT mart_student_subject_pkey PRIMARY KEY (student_id, subject_code);


--
-- Name: dq_results dq_results_pkey; Type: CONSTRAINT; Schema: audit; Owner: student_app
--

ALTER TABLE ONLY audit.dq_results
    ADD CONSTRAINT dq_results_pkey PRIMARY KEY (id);


--
-- Name: ingestion_log ingestion_log_pkey; Type: CONSTRAINT; Schema: audit; Owner: student_app
--

ALTER TABLE ONLY audit.ingestion_log
    ADD CONSTRAINT ingestion_log_pkey PRIMARY KEY (id);


--
-- Name: pipeline_runs pipeline_runs_pkey; Type: CONSTRAINT; Schema: audit; Owner: student_app
--

ALTER TABLE ONLY audit.pipeline_runs
    ADD CONSTRAINT pipeline_runs_pkey PRIMARY KEY (run_id);


--
-- Name: rejected_records rejected_records_pkey; Type: CONSTRAINT; Schema: audit; Owner: student_app
--

ALTER TABLE ONLY audit.rejected_records
    ADD CONSTRAINT rejected_records_pkey PRIMARY KEY (id);


--
-- Name: enrollment enrollment_pkey; Type: CONSTRAINT; Schema: clean; Owner: student_app
--

ALTER TABLE ONLY clean.enrollment
    ADD CONSTRAINT enrollment_pkey PRIMARY KEY (student_id, subject_code);


--
-- Name: student student_pkey; Type: CONSTRAINT; Schema: clean; Owner: student_app
--

ALTER TABLE ONLY clean.student
    ADD CONSTRAINT student_pkey PRIMARY KEY (student_id);


--
-- Name: monitoring_reports monitoring_reports_pkey; Type: CONSTRAINT; Schema: ml; Owner: student_app
--

ALTER TABLE ONLY ml.monitoring_reports
    ADD CONSTRAINT monitoring_reports_pkey PRIMARY KEY (id);


--
-- Name: risk_predictions risk_predictions_pkey; Type: CONSTRAINT; Schema: ml; Owner: student_app
--

ALTER TABLE ONLY ml.risk_predictions
    ADD CONSTRAINT risk_predictions_pkey PRIMARY KEY (id);


--
-- Name: ix_rejected_run; Type: INDEX; Schema: audit; Owner: student_app
--

CREATE INDEX ix_rejected_run ON audit.rejected_records USING btree (run_id);


--
-- Name: fact_enrollment fact_enrollment_student_key_fkey; Type: FK CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.fact_enrollment
    ADD CONSTRAINT fact_enrollment_student_key_fkey FOREIGN KEY (student_key) REFERENCES analytics.dim_student(student_key);


--
-- Name: fact_enrollment fact_enrollment_subject_key_fkey; Type: FK CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.fact_enrollment
    ADD CONSTRAINT fact_enrollment_subject_key_fkey FOREIGN KEY (subject_key) REFERENCES analytics.dim_subject(subject_key);


--
-- Name: fact_student_term fact_student_term_student_key_fkey; Type: FK CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.fact_student_term
    ADD CONSTRAINT fact_student_term_student_key_fkey FOREIGN KEY (student_key) REFERENCES analytics.dim_student(student_key);


--
-- Name: fact_student_term fact_student_term_subject_key_fkey; Type: FK CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.fact_student_term
    ADD CONSTRAINT fact_student_term_subject_key_fkey FOREIGN KEY (subject_key) REFERENCES analytics.dim_subject(subject_key);


--
-- Name: fact_student_term fact_student_term_term_key_fkey; Type: FK CONSTRAINT; Schema: analytics; Owner: student_app
--

ALTER TABLE ONLY analytics.fact_student_term
    ADD CONSTRAINT fact_student_term_term_key_fkey FOREIGN KEY (term_key) REFERENCES analytics.dim_term(term_key);


--
-- Name: enrollment enrollment_student_id_fkey; Type: FK CONSTRAINT; Schema: clean; Owner: student_app
--

ALTER TABLE ONLY clean.enrollment
    ADD CONSTRAINT enrollment_student_id_fkey FOREIGN KEY (student_id) REFERENCES clean.student(student_id);


--
-- PostgreSQL database dump complete
--

\unrestrict LADjrFzXGAoTbx1mJYrni81NG8GdU4WWDFbI2VN8uNkhyyQzv0dU7nHe1oxsfnb

