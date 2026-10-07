"""Unit tests for identifier standardisation, validation rules and transformations
(no database needed)."""
import pandas as pd
import pytest

from src.common.identity import attach_student_ids, build_registry
from src.etl import validation as v
from src.etl.analytics import attendance_pct, build_mart
from src.etl.clean import clean_records

BASE = {
    "school": "GP", "sex": "F", "age": "17", "address": "U", "famsize": "GT3", "pstatus": "T", "medu": "2",
    "fedu": "2", "mjob": "other", "fjob": "services", "reason": "course", "guardian": "mother",
    "traveltime": "1", "studytime": "2", "failures": "0", "schoolsup": "no", "famsup": "yes", "paid": "no",
    "activities": "yes", "nursery": "yes", "higher": "yes", "internet": "yes", "romantic": "no",
    "famrel": "4", "freetime": "3", "goout": "3", "dalc": "1", "walc": "2", "health": "5", "absences": "4",
    "g1": "12", "g2": "13", "g3": "13",
}


def staged(rows):
    df = pd.DataFrame(rows)
    df["source_file"] = df.get("source_file", "student-mat.csv")
    df["source_row"] = range(2, len(df) + 2)
    df["subject_code"] = df.get("subject_code", "MAT")
    return df


def test_invalid_marks_rejected():
    df = staged([BASE, {**BASE, "g3": "25", "age": "16"}, {**BASE, "g1": "-1", "age": "18"}])
    valid, rejected = v.apply_rules(df)
    assert len(valid) == 1
    assert set(rejected.rule_name) == {"invalid_marks"}


def test_domain_type_and_missing_rules():
    df = staged([{**BASE, "school": "XX"}, {**BASE, "age": "seventeen"}, {**BASE, "sex": None}, BASE])
    valid, rejected = v.apply_rules(df)
    assert len(valid) == 1
    assert sorted(rejected.rule_name) == ["invalid_category", "missing_required_field", "non_integer_value"]


def test_duplicates_removed_and_missing_attendance_imputed():
    other = {**BASE, "age": "16", "absences": None}
    df = staged([BASE, BASE, other, {**BASE, "age": "18", "absences": "10"}])
    students, enr, rejected = clean_records(df)
    assert (rejected.rule_name == "duplicate_record").sum() == 1
    assert len(enr) == 3
    imputed = enr[enr.absences_imputed]
    assert len(imputed) == 1 and imputed.absences.iloc[0] == 7  # median of 4 and 10


def test_same_student_gets_same_id_in_both_subjects():
    mat = pd.DataFrame([{**BASE}, {**BASE, "age": "16"}])
    por = pd.DataFrame([{**BASE, "g3": "15"}, {**BASE, "age": "18"}])
    reg = build_registry({"MAT": mat, "POR": por})
    a, b = attach_student_ids(mat, reg), attach_student_ids(por, reg)
    assert a.student_id.iloc[0] == b.student_id.iloc[0]          # matched on demographics
    assert reg.student_id.is_unique and len(reg) == 3
    assert all(s.startswith("STU") and len(s) == 8 for s in reg.student_id)


def test_attendance_pct_bounds():
    s = attendance_pct(pd.Series([0, 12, 500]))
    assert list(s) == [100.0, 90.0, 0.0]


def test_mart_features_and_risk():
    df = staged([{**BASE, "g1": "6", "g2": "7", "g3": "5", "failures": "2", "absences": "30"}, BASE])
    students, enr, _ = clean_records(df)
    mart = build_mart(students, enr).set_index("final_grade")
    weak, strong = mart.loc[5], mart.loc[13]
    assert weak.avg_internal_marks == pytest.approx(6.5)
    assert weak.prev_semester_grade == 7 and weak.grade_trend == 1
    assert weak.pass_status == "Fail" and weak.risk_level == "High"
    assert strong.pass_status == "Pass" and strong.risk_level == "Low"
