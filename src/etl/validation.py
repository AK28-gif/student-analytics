"""Validation rules for the UCI student records.

Each rule returns a boolean Series marking INVALID rows. Rules are pure
functions so they are unit-tested independently of the database
(tests/test_validation.py). See docs/data_dictionary.md for the rule catalogue.
"""
import pandas as pd

YES_NO = ["schoolsup", "famsup", "paid", "activities", "nursery", "higher", "internet", "romantic"]
INT_COLUMNS = ["age", "medu", "fedu", "traveltime", "studytime", "failures", "famrel", "freetime",
               "goout", "dalc", "walc", "health", "absences", "g1", "g2", "g3"]
REQUIRED = ["school", "sex", "age", "address", "famsize", "pstatus", "medu", "fedu", "mjob", "fjob",
            "reason", "nursery", "internet", "g1", "g2", "g3"]

DOMAINS = {
    "school": {"GP", "MS"},
    "sex": {"F", "M"},
    "address": {"U", "R"},
    "famsize": {"LE3", "GT3"},
    "pstatus": {"T", "A"},
    "mjob": {"teacher", "health", "services", "at_home", "other"},
    "fjob": {"teacher", "health", "services", "at_home", "other"},
    "reason": {"home", "reputation", "course", "other"},
    "guardian": {"mother", "father", "other"},
    **{c: {"yes", "no"} for c in YES_NO},
}

RANGES = {
    "age": (15, 22), "medu": (0, 4), "fedu": (0, 4), "traveltime": (1, 4), "studytime": (1, 4),
    "failures": (0, 4), "famrel": (1, 5), "freetime": (1, 5), "goout": (1, 5), "dalc": (1, 5),
    "walc": (1, 5), "health": (1, 5), "absences": (0, 93),
    "g1": (0, 20), "g2": (0, 20), "g3": (0, 20),
}


def missing_required(df: pd.DataFrame) -> pd.Series:
    return df[REQUIRED].isna().any(axis=1)


def non_numeric(df: pd.DataFrame) -> pd.Series:
    bad = pd.Series(False, index=df.index)
    for c in INT_COLUMNS:
        present = df[c].notna()
        parsed = pd.to_numeric(df[c].str.strip(), errors="coerce")
        bad |= present & (parsed.isna() | (parsed % 1 != 0))
    return bad


def out_of_domain(df: pd.DataFrame) -> pd.Series:
    bad = pd.Series(False, index=df.index)
    for c, allowed in DOMAINS.items():
        bad |= df[c].notna() & ~df[c].str.strip().isin(allowed)
    return bad


def out_of_range(df: pd.DataFrame, columns=None) -> pd.Series:
    bad = pd.Series(False, index=df.index)
    for c, (lo, hi) in RANGES.items():
        if columns and c not in columns:
            continue
        v = pd.to_numeric(df[c], errors="coerce")
        bad |= v.notna() & ((v < lo) | (v > hi))
    return bad


def duplicates(df: pd.DataFrame, subset) -> pd.Series:
    return df.duplicated(subset=subset, keep="first")


GRADE_COLUMNS = ["g1", "g2", "g3"]
NON_GRADE_RANGES = [c for c in RANGES if c not in GRADE_COLUMNS]

# Ordered rule catalogue: (rule_name, description, function)
RULES = [
    ("missing_required_field", "A required attribute (demographics or grade) is empty", missing_required),
    ("non_integer_value", "A numeric attribute is not an integer", non_numeric),
    ("invalid_category", "A categorical attribute has a value outside its documented domain", out_of_domain),
    ("invalid_marks", "A grade (G1/G2/G3) is outside the 0-20 scale",
     lambda d: out_of_range(d, GRADE_COLUMNS)),
    ("value_out_of_range", "A numeric attribute is outside its documented range",
     lambda d: out_of_range(d, NON_GRADE_RANGES)),
]


def apply_rules(df: pd.DataFrame):
    """Return (valid_df, rejected_df). rejected_df has rule_name + reason columns.
    A row is rejected by the FIRST rule it violates."""
    remaining = df.copy()
    rejected = []
    for name, desc, fn in RULES:
        mask = fn(remaining)
        if mask.any():
            rejected.append(remaining[mask].assign(rule_name=name, reason=desc))
            remaining = remaining[~mask]
    rej = pd.concat(rejected) if rejected else df.iloc[0:0].assign(rule_name=None, reason=None)
    return remaining, rej
