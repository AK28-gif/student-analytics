"""Analytics layer: star schema (dim_student, dim_subject, dim_term, fact_student_term,
fact_enrollment) and data marts (mart_student_subject, mart_subject_term_summary,
mart_student_overview). Also exports the ML feature snapshot (data/processed)."""
import numpy as np
import pandas as pd
from sqlalchemy import text

from src.common import config, db
from src.common.logging_utils import get_logger

log = get_logger("analytics")
SCHOOL_NAMES = {"GP": "Gabriel Pereira", "MS": "Mousinho da Silveira"}

# Rule-based early-warning score (Part 1). Uses only information available BEFORE the
# final grade (G3) so it can be used for intervention during the year.
RISK_RULES = [
    ("Low internal marks (<10)", 3, lambda m: m["avg_internal_marks"] < config.PASS_MARK),
    ("Previous class failures", 2, lambda m: m["prior_failures"] >= 1),
    ("Low attendance (<85%)", 2, lambda m: m["attendance_pct"] < 85),
    ("Declining grades (P1->P2 drop >= 2)", 1, lambda m: m["grade_trend"] <= -2),
    ("Very low study time (<2h/week)", 1, lambda m: m["study_time"] == 1),
    ("Does not plan higher education", 1, lambda m: ~m["wants_higher_education"].astype(bool)),
]


def attendance_pct(absences: pd.Series) -> pd.Series:
    pct = (config.SESSIONS_PER_YEAR - absences.astype(float)) / config.SESSIONS_PER_YEAR * 100
    return pct.clip(0, 100).round(2)


def score_risk(mart: pd.DataFrame) -> pd.DataFrame:
    score = pd.Series(0, index=mart.index)
    reasons = pd.Series("", index=mart.index)
    for label, points, rule in RISK_RULES:
        hit = rule(mart).fillna(False).astype(bool)
        score += np.where(hit, points, 0)
        reasons = reasons.where(~hit, reasons + np.where(reasons == "", "", "; ") + label)
    mart["risk_score"] = score.astype(int)
    mart["risk_level"] = np.select([score >= 5, score >= 3], ["High", "Medium"], default="Low")
    mart["risk_reasons"] = reasons.replace("", "None")
    return mart


def build_mart(student: pd.DataFrame, enr: pd.DataFrame) -> pd.DataFrame:
    """Pure transformation: clean tables -> mart_student_subject."""
    m = enr.merge(student, on="student_id", how="left")
    subj = pd.DataFrame([{"subject_code": k, **meta} for k, meta in config.SUBJECTS.items()])
    m = m.merge(subj[["subject_code", "subject_name", "department"]], on="subject_code")
    m["attendance_pct"] = attendance_pct(m["absences"])
    m["avg_internal_marks"] = ((m["g1"] + m["g2"]) / 2).astype(float).round(2)
    m["prev_semester_grade"] = m["g2"]
    m["grade_trend"] = m["g2"] - m["g1"]
    m["pass_status"] = np.where(m["g3"] >= config.PASS_MARK, "Pass", "Fail")
    m = m.rename(columns={
        "address": "address_type", "famsize": "family_size", "pstatus": "parent_status",
        "medu": "mother_education", "fedu": "father_education", "mjob": "mother_job", "fjob": "father_job",
        "internet": "internet_access", "higher": "wants_higher_education", "nursery": "attended_nursery",
        "traveltime": "travel_time", "studytime": "study_time", "failures": "prior_failures",
        "schoolsup": "school_support", "famsup": "family_support", "paid": "paid_classes",
        "activities": "extra_activities", "famrel": "family_relationship", "freetime": "free_time",
        "goout": "going_out", "dalc": "weekday_alcohol", "walc": "weekend_alcohol",
        "g1": "grade_p1", "g2": "grade_p2", "g3": "final_grade",
    })
    m["school_name"] = m["school"].map(SCHOOL_NAMES)
    m = score_risk(m)
    cols = [
        "student_id", "subject_code", "subject_name", "department", "school", "school_name", "sex", "age",
        "address_type", "family_size", "parent_status", "mother_education", "father_education",
        "mother_job", "father_job", "reason", "guardian", "internet_access", "wants_higher_education",
        "attended_nursery", "travel_time", "study_time", "prior_failures", "school_support",
        "family_support", "paid_classes", "extra_activities", "romantic", "family_relationship",
        "free_time", "going_out", "weekday_alcohol", "weekend_alcohol", "health", "absences",
        "attendance_pct", "absences_imputed", "grade_p1", "grade_p2", "final_grade", "avg_internal_marks",
        "prev_semester_grade", "grade_trend", "pass_status", "risk_score", "risk_level", "risk_reasons",
    ]
    return m[cols].sort_values(["student_id", "subject_code"]).reset_index(drop=True)


def build_term_long(mart: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for code, (name, order, col) in config.TERMS.items():
        src = {"g1": "grade_p1", "g2": "grade_p2", "g3": "final_grade"}[col]
        t = mart[["student_id", "subject_code", "subject_name", "department", "school", "attendance_pct"]].copy()
        t["term_code"], t["term_name"], t["term_order"], t["grade"] = code, name, order, mart[src]
        rows.append(t)
    long = pd.concat(rows, ignore_index=True).sort_values(["student_id", "subject_code", "term_order"])
    long["passed"] = long["grade"] >= config.PASS_MARK
    long["prev_term_grade"] = long.groupby(["student_id", "subject_code"])["grade"].shift(1).astype("Int64")
    long["grade_change"] = (long["grade"] - long["prev_term_grade"]).astype("Int64")
    return long


def run_analytics(run_id: str) -> dict:
    with db.transaction() as conn:
        student = pd.read_sql(text("SELECT * FROM clean.student"), conn)
        enr = pd.read_sql(text("SELECT * FROM clean.enrollment"), conn)
        for c in ["absences", "g1", "g2", "g3", "studytime", "failures"]:
            enr[c] = enr[c].astype("Int64")

        mart = build_mart(student, enr)
        long = build_term_long(mart)

        for t in ["analytics.fact_student_term", "analytics.fact_enrollment", "analytics.dim_student",
                  "analytics.dim_subject", "analytics.dim_term", "analytics.mart_student_subject",
                  "analytics.mart_subject_term_summary", "analytics.mart_student_overview"]:
            db.truncate(conn, t)

        # --- dimensions ---
        dim_student = mart.drop_duplicates("student_id")[[
            "student_id", "school", "school_name", "sex", "age", "address_type", "family_size", "parent_status",
            "mother_education", "father_education", "mother_job", "father_job", "guardian", "internet_access",
            "wants_higher_education", "travel_time", "health"]]
        dim_student.to_sql("dim_student", conn, schema="analytics", if_exists="append", index=False, method="multi")
        dim_subject = pd.DataFrame([{"subject_code": k, "subject_name": v["subject_name"], "department": v["department"]}
                                    for k, v in config.SUBJECTS.items()])
        dim_subject.to_sql("dim_subject", conn, schema="analytics", if_exists="append", index=False)
        dim_term = pd.DataFrame([{"term_code": k, "term_name": n, "term_order": o}
                                 for k, (n, o, _) in config.TERMS.items()])
        dim_term.to_sql("dim_term", conn, schema="analytics", if_exists="append", index=False)

        keys_s = pd.read_sql(text("SELECT student_key, student_id FROM analytics.dim_student"), conn)
        keys_sub = pd.read_sql(text("SELECT subject_key, subject_code FROM analytics.dim_subject"), conn)
        keys_t = pd.read_sql(text("SELECT term_key, term_code FROM analytics.dim_term"), conn)

        # --- facts ---
        fact_term = long.merge(keys_s, on="student_id").merge(keys_sub, on="subject_code").merge(keys_t, on="term_code")
        fact_term[["student_key", "subject_key", "term_key", "grade", "passed", "prev_term_grade", "grade_change"]] \
            .to_sql("fact_student_term", conn, schema="analytics", if_exists="append", index=False, method="multi")

        fe = mart.merge(keys_s, on="student_id").merge(keys_sub, on="subject_code")
        fe["passed"] = fe["pass_status"] == "Pass"
        fe[["student_key", "subject_key", "study_time", "prior_failures", "school_support", "family_support",
            "paid_classes", "extra_activities", "absences", "attendance_pct", "avg_internal_marks",
            "final_grade", "passed"]].to_sql("fact_enrollment", conn, schema="analytics", if_exists="append",
                                             index=False, method="multi")

        # --- marts ---
        mart.to_sql("mart_student_subject", conn, schema="analytics", if_exists="append", index=False, method="multi")

        summary = (long.groupby(["subject_code", "subject_name", "department", "school", "term_code", "term_name",
                                 "term_order"])
                   .agg(students=("student_id", "nunique"), avg_grade=("grade", "mean"),
                        pass_rate_pct=("passed", "mean"), fail_count=("passed", lambda s: int((~s).sum())),
                        avg_attendance_pct=("attendance_pct", "mean"))
                   .reset_index())
        summary["pass_rate_pct"] *= 100
        summary = summary.round(2)
        summary.to_sql("mart_subject_term_summary", conn, schema="analytics", if_exists="append", index=False)

        level_rank = {"Low": 0, "Medium": 1, "High": 2}
        overview = (mart.assign(rank=mart["risk_level"].map(level_rank), failed=mart["pass_status"].eq("Fail"))
                    .groupby("student_id")
                    .agg(school=("school", "first"), sex=("sex", "first"), age=("age", "first"),
                         subjects_enrolled=("subject_code", "count"), subjects_failed=("failed", "sum"),
                         avg_final_grade=("final_grade", "mean"), avg_internal_marks=("avg_internal_marks", "mean"),
                         overall_attendance_pct=("attendance_pct", "mean"), rank=("rank", "max"),
                         max_risk_score=("risk_score", "max"))
                    .reset_index())
        overview["highest_risk_level"] = overview.pop("rank").map({v: k for k, v in level_rank.items()})
        overview.round(2).to_sql("mart_student_overview", conn, schema="analytics", if_exists="append", index=False)

    # Feature snapshot for the ML pipeline / DVC (never edited by hand)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    mart.to_csv(config.FEATURES_FILE, index=False)

    stats = {"dim_student": len(dim_student), "fact_student_term": len(fact_term),
             "mart_student_subject": len(mart), "high_risk": int((mart.risk_level == "High").sum())}
    log.info("[%s] analytics layer: %s", run_id, stats)
    return stats
