"""Post-load data-quality checks. Results go to audit.dq_results; any failed
'critical' check fails the pipeline run (and therefore the Airflow task)."""
from sqlalchemy import text

from src.common import db
from src.common.logging_utils import get_logger

log = get_logger("quality")

# (check_name, table, severity, SQL returning one number, expectation(value, ctx) -> bool, expectation text)
CHECKS = [
    ("staging_not_empty", "staging.stg_uci_student", "critical",
     "SELECT count(*) FROM staging.stg_uci_student", lambda v: v > 0, "> 0 rows"),
    ("staging_matches_ingested_rows", "staging.stg_uci_student", "critical",
     """SELECT (SELECT count(*) FROM staging.stg_uci_student WHERE _run_id = :run_id)
             - (SELECT coalesce(sum(row_count), 0) FROM audit.ingestion_log
                WHERE run_id = :run_id AND status = 'SUCCESS')""",
     lambda v: v == 0, "staged rows = ingested rows"),
    ("clean_retention_rate", "clean.enrollment", "critical",
     """SELECT 100.0 * (SELECT count(*) FROM clean.enrollment)
             / NULLIF((SELECT count(*) FROM staging.stg_uci_student), 0)""",
     lambda v: v >= 95, ">= 95% of staged rows survive cleaning"),
    ("student_id_unique", "analytics.dim_student", "critical",
     "SELECT count(*) - count(DISTINCT student_id) FROM analytics.dim_student", lambda v: v == 0, "0 duplicates"),
    ("student_id_format", "analytics.dim_student", "critical",
     "SELECT count(*) FROM analytics.dim_student WHERE student_id !~ '^STU[0-9]{5}$'", lambda v: v == 0,
     "all ids match STU#####"),
    ("grades_in_range", "analytics.fact_student_term", "critical",
     "SELECT count(*) FROM analytics.fact_student_term WHERE grade NOT BETWEEN 0 AND 20", lambda v: v == 0,
     "0 grades outside 0-20"),
    ("attendance_in_range", "analytics.mart_student_subject", "critical",
     "SELECT count(*) FROM analytics.mart_student_subject WHERE attendance_pct NOT BETWEEN 0 AND 100",
     lambda v: v == 0, "0 values outside 0-100"),
    ("fact_term_grain", "analytics.fact_student_term", "critical",
     "SELECT (SELECT count(*) FROM analytics.fact_student_term) - 3 * (SELECT count(*) FROM clean.enrollment)",
     lambda v: v == 0, "3 term rows per enrolment"),
    ("mart_matches_enrollment", "analytics.mart_student_subject", "critical",
     "SELECT (SELECT count(*) FROM analytics.mart_student_subject) - (SELECT count(*) FROM clean.enrollment)",
     lambda v: v == 0, "1 mart row per enrolment"),
    ("no_orphan_facts", "analytics.fact_enrollment", "critical",
     """SELECT count(*) FROM analytics.fact_enrollment f
        LEFT JOIN analytics.dim_student d USING (student_key) WHERE d.student_key IS NULL""",
     lambda v: v == 0, "every fact row has a student"),
    ("rejected_share_pct", "audit.rejected_records", "warning",
     """SELECT 100.0 * (SELECT count(*) FROM audit.rejected_records WHERE run_id = :run_id)
             / NULLIF((SELECT count(*) FROM staging.stg_uci_student), 0)""",
     lambda v: v < 5, "< 5% of rows rejected"),
    ("students_in_both_subjects", "clean.enrollment", "warning",
     """SELECT count(*) FROM (SELECT student_id FROM clean.enrollment GROUP BY student_id
                              HAVING count(*) = 2) x""",
     lambda v: 300 <= v <= 400, "300-400 (UCI documents 382)"),
    ("final_grade_zero_share_pct", "clean.enrollment", "warning",
     "SELECT 100.0 * avg((g3 = 0)::int) FROM clean.enrollment",
     lambda v: v < 10, "< 10% (G3=0 usually means the student missed the final exam)"),
    ("imputed_attendance_share_pct", "clean.enrollment", "warning",
     "SELECT 100.0 * avg(absences_imputed::int) FROM clean.enrollment",
     lambda v: v < 10, "< 10% of attendance values imputed"),
]


class DataQualityError(RuntimeError):
    pass


def run_quality_checks(run_id: str) -> list:
    results = []
    with db.transaction() as conn:
        for name, table, severity, sql, expect, expectation in CHECKS:
            value = conn.execute(text(sql), {"run_id": run_id}).scalar()
            value = float(value) if value is not None else None
            passed = value is not None and bool(expect(value))
            conn.execute(text("""INSERT INTO audit.dq_results (run_id, check_name, table_name, severity, passed,
                                     observed_value, expectation)
                                 VALUES (:r, :n, :t, :s, :p, :v, :e)"""),
                         {"r": run_id, "n": name, "t": table, "s": severity, "p": passed, "v": value, "e": expectation})
            results.append({"check": name, "severity": severity, "passed": passed, "value": value})
            log.info("[%s] DQ %-32s %-8s %s (observed=%s, expected %s)", run_id, name, severity,
                     "PASS" if passed else "FAIL", value, expectation)
    failed = [r["check"] for r in results if r["severity"] == "critical" and not r["passed"]]
    if failed:
        raise DataQualityError(f"Critical data-quality checks failed: {failed}")
    return results
