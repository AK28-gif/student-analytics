"""FastAPI inference service for the student fail-risk model.

    uvicorn api.main:app --reload --port 8000        (local)
    docker compose up --build api                    (container)

Every request is appended to a JSON-lines prediction log (inputs, outputs, latency,
status) which src/ml/monitor.py uses for drift, latency and failure monitoring.
"""
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

import joblib
import numpy as np
import pandas as pd
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.ml.features import prepare_frame, risk_band

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = Path(os.getenv("MODEL_DIR", ROOT / "models" / "champion"))
PREDICTION_LOG = Path(os.getenv("PREDICTION_LOG", ROOT / "logs" / "api" / "predictions.jsonl"))

STATE = {"model": None, "meta": None, "params": None, "latencies": [], "requests": 0, "errors": 0}


class StudentFeatures(BaseModel):
    subject_code: Literal["MAT", "POR"] = Field(..., description="MAT = Mathematics, POR = Portuguese")
    school: Literal["GP", "MS"]
    sex: Literal["F", "M"]
    age: int = Field(..., ge=15, le=22)
    address_type: Literal["U", "R"]
    family_size: Literal["LE3", "GT3"]
    parent_status: Literal["T", "A"]
    mother_education: int = Field(..., ge=0, le=4)
    father_education: int = Field(..., ge=0, le=4)
    mother_job: Literal["teacher", "health", "services", "at_home", "other"]
    father_job: Literal["teacher", "health", "services", "at_home", "other"]
    reason: Literal["home", "reputation", "course", "other"]
    guardian: Literal["mother", "father", "other"]
    travel_time: int = Field(..., ge=1, le=4)
    study_time: int = Field(..., ge=1, le=4)
    prior_failures: int = Field(..., ge=0, le=4)
    family_relationship: int = Field(..., ge=1, le=5)
    free_time: int = Field(..., ge=1, le=5)
    going_out: int = Field(..., ge=1, le=5)
    weekday_alcohol: int = Field(..., ge=1, le=5)
    weekend_alcohol: int = Field(..., ge=1, le=5)
    health: int = Field(..., ge=1, le=5)
    absences: int = Field(..., ge=0, le=93)
    attendance_pct: Optional[float] = Field(None, ge=0, le=100, description="derived from absences if omitted")
    grade_p1: int = Field(..., ge=0, le=20)
    grade_p2: int = Field(..., ge=0, le=20)
    school_support: bool
    family_support: bool
    paid_classes: bool
    extra_activities: bool
    attended_nursery: bool
    wants_higher_education: bool
    internet_access: bool
    romantic: bool
    student_id: Optional[str] = None

    model_config = {"json_schema_extra": {"example": {
        "subject_code": "MAT", "school": "GP", "sex": "F", "age": 17, "address_type": "U", "family_size": "GT3",
        "parent_status": "T", "mother_education": 2, "father_education": 2, "mother_job": "services",
        "father_job": "other", "reason": "course", "guardian": "mother", "travel_time": 2, "study_time": 1,
        "prior_failures": 1, "family_relationship": 4, "free_time": 3, "going_out": 4, "weekday_alcohol": 1,
        "weekend_alcohol": 3, "health": 3, "absences": 14, "grade_p1": 8, "grade_p2": 7, "school_support": False,
        "family_support": True, "paid_classes": False, "extra_activities": False, "attended_nursery": True,
        "wants_higher_education": True, "internet_access": True, "romantic": False, "student_id": "STU00042"}}}


class Prediction(BaseModel):
    student_id: Optional[str]
    fail_probability: float
    predicted_fail: bool
    risk_band: str
    model_version: str
    model_type: str


def _load_model():
    STATE["model"] = joblib.load(MODEL_DIR / "model.joblib")
    STATE["meta"] = json.loads((MODEL_DIR / "metadata.json").read_text())
    STATE["params"] = yaml.safe_load((MODEL_DIR / "params.yaml").read_text())


@asynccontextmanager
async def lifespan(_app):
    _load_model()
    yield


app = FastAPI(title="Student Dropout/Fail-Risk API", version="1.0.0", lifespan=lifespan,
              description="Predicts the probability that a student fails a subject (final grade < 10/20).")


def _log(record: dict) -> None:
    PREDICTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PREDICTION_LOG, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def _enrich(s: StudentFeatures) -> dict:
    d = s.model_dump()
    sessions = int(os.getenv("SESSIONS_PER_YEAR", "120"))
    if d["attendance_pct"] is None:
        d["attendance_pct"] = round(max(0.0, min(100.0, (sessions - d["absences"]) / sessions * 100)), 2)
    d["avg_internal_marks"] = (d["grade_p1"] + d["grade_p2"]) / 2
    d["grade_trend"] = d["grade_p2"] - d["grade_p1"]
    return d


def _predict(records: List[dict]) -> List[Prediction]:
    meta = STATE["meta"]
    X = prepare_frame(pd.DataFrame(records), STATE["params"])
    proba = STATE["model"].predict_proba(X)[:, 1]
    return [Prediction(student_id=r.get("student_id"), fail_probability=round(float(p), 4),
                       predicted_fail=bool(p >= meta["decision_threshold"]), risk_band=risk_band(float(p)),
                       model_version=meta["model_version"], model_type=meta["model_type"])
            for r, p in zip(records, proba)]


def _serve(students: List[StudentFeatures]) -> List[Prediction]:
    start = time.perf_counter()
    rid = str(uuid.uuid4())
    records = [_enrich(s) for s in students]
    STATE["requests"] += 1
    try:
        preds = _predict(records)
    except Exception as exc:
        STATE["errors"] += 1
        _log({"ts": datetime.now(timezone.utc).isoformat(), "request_id": rid, "status": "error",
              "error": str(exc), "latency_ms": round((time.perf_counter() - start) * 1000, 2)})
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}")
    latency = round((time.perf_counter() - start) * 1000, 2)
    STATE["latencies"] = (STATE["latencies"] + [latency])[-1000:]
    for rec, p in zip(records, preds):
        _log({"ts": datetime.now(timezone.utc).isoformat(), "request_id": rid, "status": "ok",
              "latency_ms": latency, "model_version": p.model_version, "input": rec, "output": p.model_dump()})
    return preds


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    STATE["errors"] += 1
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok" if STATE["model"] is not None else "model not loaded",
            "model_version": (STATE["meta"] or {}).get("model_version")}


@app.get("/model")
def model_info():
    return STATE["meta"]


@app.get("/metrics")
def metrics():
    lat = STATE["latencies"]
    return {"requests": STATE["requests"], "errors": STATE["errors"],
            "latency_ms_p50": float(np.percentile(lat, 50)) if lat else None,
            "latency_ms_p95": float(np.percentile(lat, 95)) if lat else None}


@app.post("/predict", response_model=Prediction)
def predict(student: StudentFeatures):
    return _serve([student])[0]


@app.post("/predict/batch", response_model=List[Prediction])
def predict_batch(students: List[StudentFeatures]):
    if not students:
        raise HTTPException(status_code=422, detail="Empty batch")
    return _serve(students)


@app.post("/reload")
def reload_model():
    """Hot-reload after a new champion has been exported (e.g. by the Airflow ML DAG)."""
    _load_model()
    return health()
