"""Airflow DAG - Part 2 MLOps pipeline.

Triggered automatically whenever the Part 1 DAG refreshes the analytics mart (Airflow Dataset).

monitor_drift -> train_and_register -> batch_score

The model is retrained (and a new MLflow model version registered) on every run, i.e. every
time the data pipeline refreshes the mart. monitor_drift runs first so each run also records a
drift / performance report comparing the new data with the previous model's training data.
"""
import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# macOS fix: Airflow forks a child process per task. If pyarrow (imported by pandas) is first
# loaded INSIDE that forked child, its bundled curl asks macOS for proxy settings and deadlocks.
# Loading it here, in the parent process that parses this file, avoids the problem.
try:
    import pyarrow  # noqa: F401
except ImportError:
    pass

STUDENT_MART = Dataset("postgres://localhost:5432/student_db/analytics/mart_student_subject")


def _monitor(**_):
    from src.common import config
    if not (config.CHAMPION_DIR / "model.joblib").exists():
        return {"retrain_recommended": True, "reasons": ["no champion model yet"]}
    from src.ml.monitor import run_monitoring
    report = run_monitoring("mart")
    return {"retrain_recommended": report["retrain_recommended"], "reasons": report["reasons"]}


def _train(**_):
    from src.ml.train import main
    main()


def _score(**_):
    from src.ml.predict import run_batch_scoring
    return run_batch_scoring()


with DAG(
    dag_id="student_risk_ml_pipeline",
    description="Drift monitoring -> retraining (MLflow registry) -> batch risk scoring",
    default_args={"owner": "student-analytics", "retries": 1, "retry_delay": timedelta(minutes=2)},
    schedule=[STUDENT_MART],
    start_date=datetime(2026, 9, 1),
    catchup=False,
    max_active_runs=1,
    tags=["ml", "mlops", "part2"],
) as dag:
    monitor = PythonOperator(task_id="monitor_drift", python_callable=_monitor)
    train = PythonOperator(task_id="train_and_register", python_callable=_train)
    score = PythonOperator(task_id="batch_score", python_callable=_score)

    monitor >> train >> score
