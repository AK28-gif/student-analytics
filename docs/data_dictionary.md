# Data Dictionary & Validation Rules

All tables live in the PostgreSQL database `student_db`. There are five schemas, one per layer:

| Schema | Layer | What it holds |
|---|---|---|
| `staging` | Staging | Source rows exactly as downloaded (every column is TEXT) + where they came from |
| `clean` | Cleaned | Typed, validated, de-duplicated records with a standard `student_id` |
| `analytics` | Analytical | Star schema (dimensions + facts) and data marts used by the dashboard and the ML model |
| `ml` | MLOps (Part 2) | Batch predictions and monitoring reports |
| `audit` | Logging | Pipeline runs, ingestion log, rejected records, data-quality results |

The **raw layer** is on disk: `data/raw/<run_id>/` holds the downloaded zip, the two CSV files and a `manifest.json` (row counts + SHA-256 checksums).

---

## 1. Source: UCI Student Performance dataset

Each row is one student in one subject (Mathematics file `student-mat.csv`, Portuguese file `student-por.csv`). Separator `;`.

| Source column | Meaning | Allowed values |
|---|---|---|
| school | School | `GP` Gabriel Pereira, `MS` Mousinho da Silveira |
| sex | Sex | `F`, `M` |
| age | Age in years | 15 – 22 |
| address | Home address type | `U` urban, `R` rural |
| famsize | Family size | `LE3` ≤ 3, `GT3` > 3 |
| Pstatus | Parents' cohabitation | `T` together, `A` apart |
| Medu / Fedu | Mother's / father's education | 0 none, 1 primary (4th grade), 2 5th–9th grade, 3 secondary, 4 higher |
| Mjob / Fjob | Mother's / father's job | teacher, health, services, at_home, other |
| reason | Reason for choosing the school | home, reputation, course, other |
| guardian | Student's guardian | mother, father, other |
| traveltime | Home-to-school travel time | 1 <15 min, 2 15–30 min, 3 30–60 min, 4 >1 h |
| studytime | Weekly study time | 1 <2 h, 2 2–5 h, 3 5–10 h, 4 >10 h |
| failures | Past class failures | 0 – 3 (4 = 4 or more) |
| schoolsup, famsup, paid, activities, nursery, higher, internet, romantic | Extra school support, family support, paid extra classes, extra-curricular activities, attended nursery, wants higher education, internet at home, in a relationship | yes / no |
| famrel, freetime, goout, Dalc, Walc, health | Family relationship quality, free time, going out, weekday / weekend alcohol use, health status | 1 (very low/bad) – 5 (very high/good) |
| absences | Number of school absences in the subject | 0 – 93 |
| G1, G2 | First and second period grade (internal marks) | 0 – 20 |
| G3 | Final grade (the outcome) | 0 – 20 |

---

## 2. Validation rules

Rules run in `src/etl/validation.py` and `src/etl/clean.py`. A row that breaks a rule is **not** loaded into `clean`. Instead it goes to `audit.rejected_records` (and `logs/rejected_records.log`) with the rule name, the reason and the full original record.

| # | Rule | Check | Action |
|---|---|---|---|
| R1 | `malformed_line` | CSV line has the wrong number of fields | rejected at ingestion |
| R2 | `missing_required_field` | school, sex, age, address, famsize, Pstatus, Medu, Fedu, Mjob, Fjob, reason, nursery, internet, G1, G2 or G3 is empty | rejected |
| R3 | `non_integer_value` | a numeric column is not a whole number | rejected |
| R4 | `invalid_category` | a categorical column has a value outside the allowed list above | rejected |
| R5 | `invalid_marks` | G1, G2 or G3 is outside 0–20 | rejected |
| R6 | `value_out_of_range` | any other numeric column outside its range above | rejected |
| R7 | `duplicate_record` | exact copy of an earlier row in the same file | duplicate rejected, first kept |
| R8 | `duplicate_student_subject` | same student twice in the same subject | duplicate rejected, first kept |
| — | Missing attendance | `absences` empty | **kept**: filled with the subject median, `absences_imputed = true` |

### Data-quality checks after loading (`src/etl/quality.py` → `audit.dq_results`)

A failed **critical** check stops the pipeline run.

| Check | Severity | Expectation |
|---|---|---|
| staging_not_empty | critical | > 0 rows |
| staging_matches_ingested_rows | critical | staged rows = rows logged at ingestion |
| clean_retention_rate | critical | ≥ 95 % of staged rows survive cleaning |
| student_id_unique | critical | no duplicate ids in `dim_student` |
| student_id_format | critical | every id matches `STU#####` |
| grades_in_range | critical | every grade within 0–20 |
| attendance_in_range | critical | every attendance % within 0–100 |
| fact_term_grain | critical | exactly 3 term rows per enrolment |
| mart_matches_enrollment | critical | 1 mart row per enrolment |
| no_orphan_facts | critical | every fact row has a student |
| rejected_share_pct | warning | < 5 % of rows rejected |
| students_in_both_subjects | warning | 300–400 (UCI documents 382) |
| final_grade_zero_share_pct | warning | < 10 % with G3 = 0 (usually a missed final exam, a possible dropout signal) |
| imputed_attendance_share_pct | warning | < 10 % attendance values imputed |

---

## 3. Student identifier standardisation

The UCI files have **no student id**, and many students appear in both files. Following the dataset authors' own merge script (`student-merge.R`), a student is matched by 13 attributes: school, sex, age, address, famsize, Pstatus, Medu, Fedu, Mjob, Fjob, reason, nursery, internet.

1. `match_key` = SHA-1 hash of those 13 values.
2. If two different students share the same key in a file, `occurrence` (0, 1, …) tells them apart.
3. Every distinct (match_key, occurrence) pair gets a canonical id `STU00001`, `STU00002`, …
4. A student found in both files therefore gets the **same id** in Mathematics and Portuguese.

---

## 4. Derived features (formulas)

| Feature | Formula |
|---|---|
| `attendance_pct` | (120 − absences) / 120 × 100, clipped to 0–100. **Assumption:** 120 scheduled sessions per subject per year (UCI only gives the absence count; configurable with `SESSIONS_PER_YEAR`). |
| `avg_internal_marks` | (G1 + G2) / 2 |
| `prev_semester_grade` | G2 (the most recent term before the final) |
| `grade_trend` | G2 − G1 |
| `pass_status` | `Pass` if G3 ≥ 10 else `Fail` |
| `prev_term_grade`, `grade_change` (fact_student_term) | grade of the previous term and the difference |
| `risk_score` (rule-based, Part 1) | sum of points: internal marks < 10 → 3, past failures ≥ 1 → 2, attendance < 85 % → 2, G2 − G1 ≤ −2 → 1, study time < 2 h → 1, doesn't want higher education → 1 |
| `risk_level` | High if score ≥ 5, Medium if 3–4, Low otherwise |

The rule-based risk score deliberately does **not** use G3, so it can flag students *before* the final exam.

---

## 5. Tables

### staging.stg_uci_student
All 33 source columns (lower-case names, TEXT) plus:

| Column | Description |
|---|---|
| source_file | `student-mat.csv` or `student-por.csv` |
| source_row | line number in the CSV (header = 1) |
| subject_code | `MAT` or `POR` |
| _run_id | pipeline run that loaded the row |
| _loaded_at | load timestamp |

### clean.student (1 row per student)
`student_id` (PK), `match_key`, and the demographic / background columns from the source, typed (SMALLINT, BOOLEAN). If a student is in both files, the Mathematics row is used for demographics.

### clean.enrollment (1 row per student × subject)
| Column | Type | Description |
|---|---|---|
| student_id, subject_code | TEXT | primary key |
| studytime, failures | SMALLINT | |
| schoolsup, famsup, paid, activities | BOOLEAN | |
| absences | SMALLINT | after imputation |
| absences_imputed | BOOLEAN | true if absences was missing |
| g1, g2, g3 | SMALLINT | grades 0–20 |

### analytics.dim_student
`student_key` (surrogate PK), `student_id`, `school`, `school_name`, `sex`, `age`, `address_type`, `family_size`, `parent_status`, `mother_education`, `father_education`, `mother_job`, `father_job`, `guardian`, `internet_access`, `wants_higher_education`, `travel_time`, `health`.

### analytics.dim_subject
| subject_key | subject_code | subject_name | department |
|---|---|---|---|
| 1 | MAT | Mathematics | Science & Mathematics |
| 2 | POR | Portuguese Language | Languages & Humanities |

### analytics.dim_term
| term_code | term_name | term_order | source column |
|---|---|---|---|
| P1 | Period 1 | 1 | G1 |
| P2 | Period 2 | 2 | G2 |
| P3 | Final | 3 | G3 |

### analytics.fact_student_term (grain: student × subject × term)
`student_key`, `subject_key`, `term_key`, `grade`, `passed` (grade ≥ 10), `prev_term_grade`, `grade_change`.

### analytics.fact_enrollment (grain: student × subject)
`student_key`, `subject_key`, `study_time`, `prior_failures`, `school_support`, `family_support`, `paid_classes`, `extra_activities`, `absences`, `attendance_pct`, `avg_internal_marks`, `final_grade`, `passed`.

### analytics.mart_student_subject (data mart, 1 row per student × subject)
A wide, ready-to-use table that joins all of the above. It contains every student attribute (readable names), `grade_p1`, `grade_p2`, `final_grade`, `avg_internal_marks`, `prev_semester_grade`, `grade_trend`, `absences`, `attendance_pct`, `absences_imputed`, `pass_status`, `risk_score`, `risk_level` and `risk_reasons`. It feeds the dashboard and is exported to `data/processed/student_features.csv` for ML.

### analytics.mart_subject_term_summary (subject × school × term)
`students`, `avg_grade`, `pass_rate_pct`, `fail_count`, `avg_attendance_pct`, used for the department and term views.

### analytics.mart_student_overview (1 row per student)
`subjects_enrolled`, `subjects_failed`, `avg_final_grade`, `avg_internal_marks`, `overall_attendance_pct`, `highest_risk_level`, `max_risk_score`.

### ml.risk_predictions
`scored_at`, `model_name`, `model_version`, `model_type`, `student_id`, `subject_code`, `fail_probability`, `predicted_fail`, `risk_band` (High ≥ 0.6, Medium ≥ 0.3, Low), `actual_fail`.

### ml.monitoring_reports
`created_at`, `model_version`, `dataset`, `drift_share`, `drifted_features`, `reference_positive_rate`, `current_positive_rate`, `reference_f1`, `current_f1`, `api_requests`, `api_error_rate`, `api_p95_latency_ms`, `retrain_recommended`, `reasons`, `report` (full JSON).

### audit tables
| Table | Columns |
|---|---|
| pipeline_runs | run_id, started_at, finished_at, status, triggered_by (cli/airflow), message |
| ingestion_log | run_id, source_name, source_type, source_location, extracted_at, status, row_count, failed_row_count, raw_path, checksum_sha256, error_message |
| rejected_records | run_id, stage, source_name, rule_name, record_key (file:line), reason, record (JSON), logged_at |
| dq_results | run_id, check_name, table_name, severity, passed, observed_value, expectation, checked_at |
