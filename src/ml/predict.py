"""Batch scoring: score every student x subject in the analytics mart with the champion
model and store results in ml.risk_predictions (read by the Streamlit dashboard).

    python -m src.ml.predict
"""
import json

import joblib
import pandas as pd
from sqlalchemy import text

from src.common import config, db
from src.common.logging_utils import get_logger
from src.ml.features import load_params, make_target, prepare_frame, risk_band

log = get_logger("predict")


def load_champion():
    model = joblib.load(config.CHAMPION_DIR / "model.joblib")
    meta = json.loads((config.CHAMPION_DIR / "metadata.json").read_text())
    return model, meta


def run_batch_scoring() -> int:
    params = load_params(config.CHAMPION_DIR / "params.yaml")
    model, meta = load_champion()
    with db.transaction() as conn:
        mart = pd.read_sql(text("SELECT * FROM analytics.mart_student_subject"), conn)
    proba = model.predict_proba(prepare_frame(mart, params))[:, 1]
    out = pd.DataFrame({
        "model_name": meta["model_name"], "model_version": meta["model_version"], "model_type": meta["model_type"],
        "student_id": mart["student_id"], "subject_code": mart["subject_code"],
        "fail_probability": proba.round(4), "predicted_fail": proba >= meta["decision_threshold"],
        "risk_band": [risk_band(p) for p in proba], "actual_fail": make_target(mart, params).astype(bool),
    })
    with db.transaction() as conn:
        conn.execute(text("DELETE FROM ml.risk_predictions WHERE model_version = :v"), {"v": meta["model_version"]})
        out.to_sql("risk_predictions", conn, schema="ml", if_exists="append", index=False, method="multi")
    log.info("Scored %s enrolments with %s v%s (%s predicted to fail)", len(out), meta["model_type"],
             meta["model_version"], int(out.predicted_fail.sum()))
    return len(out)


if __name__ == "__main__":
    run_batch_scoring()
