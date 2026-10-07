"""Student identifier standardisation.

The UCI dataset ships two files (Mathematics and Portuguese) without a student id.
Following the dataset authors' own merge script (student-merge.R) a student is
identified by 13 demographic attributes. We build a deterministic registry from
(match_key, occurrence) pairs and assign canonical ids STU00001, STU00002, ...
A student who appears in both files therefore gets the SAME id in both subjects.
"""
import hashlib

import pandas as pd

MATCH_COLUMNS = [
    "school", "sex", "age", "address", "famsize", "pstatus", "medu", "fedu",
    "mjob", "fjob", "reason", "nursery", "internet",
]


def canonical_id(number: int) -> str:
    return f"STU{int(number):05d}"


def match_key(df: pd.DataFrame) -> pd.Series:
    joined = df[MATCH_COLUMNS].astype(str).apply(lambda r: "|".join(v.strip().lower() for v in r), axis=1)
    return joined.map(lambda s: hashlib.sha1(s.encode()).hexdigest()[:16])


def build_registry(frames: dict) -> pd.DataFrame:
    """frames: {subject_code: dataframe with MATCH_COLUMNS}. Returns the frames' rows
    annotated with match_key/occurrence plus a registry mapping -> student_id."""
    pairs = []
    for subject, df in frames.items():
        keys = match_key(df)
        occ = keys.groupby(keys).cumcount()
        pairs.append(pd.DataFrame({"match_key": keys.values, "occurrence": occ.values}))
    registry = (
        pd.concat(pairs).drop_duplicates().sort_values(["match_key", "occurrence"]).reset_index(drop=True)
    )
    registry["student_id"] = [canonical_id(i + 1) for i in range(len(registry))]
    return registry


def attach_student_ids(df: pd.DataFrame, registry: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["match_key"] = match_key(out).values
    out["occurrence"] = out.groupby("match_key").cumcount().values
    return out.merge(registry, on=["match_key", "occurrence"], how="left")

