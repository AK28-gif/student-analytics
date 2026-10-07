"""Feature definitions shared by training, batch scoring, monitoring and the FastAPI service."""
from pathlib import Path

import pandas as pd
import yaml

PARAMS_PATH = Path(__file__).resolve().parents[2] / "params.yaml"


def load_params(path=PARAMS_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def feature_lists(params: dict):
    f = params["features"]
    return f["numeric"], f["categorical"], f["boolean"]


def all_features(params: dict) -> list:
    num, cat, boo = feature_lists(params)
    return num + cat + boo


def prepare_frame(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Select model inputs and coerce types consistently (booleans -> 0/1, numerics -> float)."""
    num, cat, boo = feature_lists(params)
    missing = [c for c in num + cat + boo if c not in df.columns]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")
    X = pd.DataFrame(index=df.index)
    for c in num:
        X[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    for c in cat:
        X[c] = df[c].astype(str)
    for c in boo:
        X[c] = df[c].map(lambda x: 1.0 if str(x).lower() in ("true", "1", "yes", "1.0") else 0.0)
    return X


def make_target(df: pd.DataFrame, params: dict) -> pd.Series:
    return (pd.to_numeric(df["final_grade"]) < params["target"]["pass_mark"]).astype(int)


def risk_band(prob: float) -> str:
    return "High" if prob >= 0.6 else "Medium" if prob >= 0.3 else "Low"
