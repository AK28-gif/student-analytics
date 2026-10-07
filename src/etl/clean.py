"""Clean layer: validate staging rows, remove duplicates / invalid marks, standardise
student identifiers across the two subject files, handle missing attendance, and
load typed tables clean.student + clean.enrollment. Every rejected row is written to
audit.rejected_records and logs/rejected_records.log with the rule it broke."""
import json
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import text

from src.common import config, db
from src.common.identity import attach_student_ids, build_registry
from src.common.logging_utils import get_logger
from src.etl import validation as v

log = get_logger("clean")

STUDENT_COLS = ["student_id", "match_key", "school", "sex", "age", "address", "famsize", "pstatus",
                "medu", "fedu", "mjob", "fjob", "reason", "guardian", "traveltime", "nursery", "internet",
                "higher", "romantic", "famrel", "freetime", "goout", "dalc", "walc", "health"]
ENROLL_COLS = ["student_id", "subject_code", "studytime", "failures", "schoolsup", "famsup", "paid",
               "activities", "absences", "absences_imputed", "g1", "g2", "g3"]
DATA_COLS = [c for c in v.REQUIRED + v.INT_COLUMNS + list(v.DOMAINS)]


def _log_rejections(conn, run_id: str, rejected: pd.DataFrame) -> None:
    if rejected.empty:
        return
    payload_cols = [c for c in rejected.columns if c not in ("rule_name", "reason", "_run_id", "_loaded_at")]
    rows = [{
        "run_id": run_id, "stage": "cleaning", "source_name": r["source_file"], "rule_name": r["rule_name"],
        "record_key": f"{r['source_file']}:line {r['source_row']}", "reason": r["reason"],
        "record": json.dumps({c: (None if pd.isna(r[c]) else str(r[c])) for c in payload_cols}),
    } for _, r in rejected.iterrows()]
    conn.execute(
        text("""INSERT INTO audit.rejected_records (run_id, stage, source_name, rule_name, record_key, reason, record)
                   VALUES (:run_id, :stage, :source_name, :rule_name, :record_key, :reason, CAST(:record AS JSONB))"""),
        rows,
    )
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.REJECTED_LOG, "a") as f:
        for r in rows:
            f.write(f"{datetime.now(timezone.utc).isoformat()} | run={r['run_id']} | {r['record_key']} | "
                    f"rule={r['rule_name']} | {r['reason']}\n")


def clean_records(staged: pd.DataFrame):
    """Pure transformation (unit-testable). Returns (students, enrollments, rejected)."""
    df = staged.copy()
    for c in DATA_COLS:
        df[c] = df[c].where(df[c].isna(), df[c].astype(str).str.strip())

    # 1) rule-based validation (missing fields, types, domains, invalid marks, ranges)
    valid, rejected = v.apply_rules(df)

    # 2) exact duplicate records inside the same subject file
    dup = v.duplicates(valid, ["subject_code"] + DATA_COLS)
    rejected = pd.concat([rejected, valid[dup].assign(rule_name="duplicate_record",
                                                      reason="Exact duplicate of an earlier row in the same file")])
    valid = valid[~dup].copy()

    # 3) type casting
    for c in v.INT_COLUMNS:
        valid[c] = pd.to_numeric(valid[c]).astype("Int64")
    for c in v.YES_NO:
        valid[c] = valid[c].map({"yes": True, "no": False})

    # 4) missing attendance (absences): impute with the subject median and flag it
    valid["absences_imputed"] = valid["absences"].isna()
    medians = valid.groupby("subject_code")["absences"].transform("median").round()
    valid["absences"] = valid["absences"].fillna(medians).astype("Int64")

    # 5) standardise student identifiers across Mathematics + Portuguese files
    frames = {s: g for s, g in valid.groupby("subject_code")}
    registry = build_registry(frames)
    valid = pd.concat([attach_student_ids(g, registry) for g in frames.values()], ignore_index=True)

    # 6) one enrolment per (student, subject) - defensive, should never trigger
    dup_key = v.duplicates(valid, ["student_id", "subject_code"])
    rejected = pd.concat([rejected, valid[dup_key].assign(rule_name="duplicate_student_subject",
                                                          reason="Second enrolment for the same student and subject")])
    valid = valid[~dup_key]

    # Demographics: first occurrence per student (Mathematics file first, then Portuguese)
    students = valid.sort_values(["subject_code", "source_row"]).drop_duplicates("student_id")[STUDENT_COLS]
    enrollments = valid[ENROLL_COLS]
    return students.reset_index(drop=True), enrollments.reset_index(drop=True), rejected


def run_clean(run_id: str) -> dict:
    with db.transaction() as conn:
        staged = pd.read_sql(text("SELECT * FROM staging.stg_uci_student WHERE _run_id = :r"), conn,
                             params={"r": run_id})
        students, enrollments, rejected = clean_records(staged)
        _log_rejections(conn, run_id, rejected)
        db.truncate(conn, "clean.student")      # cascades to clean.enrollment
        students.to_sql("student", conn, schema="clean", if_exists="append", index=False, method="multi")
        enrollments.to_sql("enrollment", conn, schema="clean", if_exists="append", index=False, method="multi")
    stats = {"staged": len(staged), "students": len(students), "enrollments": len(enrollments),
             "rejected": len(rejected),
             "in_both_subjects": int(enrollments.groupby("student_id").size().eq(2).sum())}
    log.info("[%s] clean layer: %s", run_id, stats)
    return stats
