"""Airflow DAG - Part 1 data pipeline.

start_run -> extract_uci_source -> load_staging -> clean_and_validate
          -> build_analytics_marts -> data_quality_checks -> finish_run
Runs daily; each task is idempotent for a given run_id (passed via XCom).
"""
import os
import re
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator
from airflow.utils.trigger_rule import TriggerRule

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

# Emitted when the analytics mart has been rebuilt successfully -> triggers the ML DAG
STUDENT_MART = Dataset("postgres://localhost:5432/student_db/analytics/mart_student_subject")


def _start(**ctx):
    from src.pipeline import start_run
    # e.g. manual__2026-09-07T10:00:00+00:00 -> airflow_manual__2026_09_07T10_00_00_00_00
    return start_run("airflow", run_id="airflow_" + re.sub(r"[^A-Za-z0-9]", "_", ctx["run_id"]))


def _rid(ctx):
    return ctx["ti"].xcom_pull(task_ids="start_run")


def _ingest(**ctx):
    from src.ingestion.ingest import run_ingestion
    return run_ingestion(_rid(ctx))


def _staging(**ctx):
    from src.etl.staging import load_staging
    return load_staging(_rid(ctx))


def _clean(**ctx):
    from src.etl.clean import run_clean
    return run_clean(_rid(ctx))


def _analytics(**ctx):
    from src.etl.analytics import run_analytics
    return run_analytics(_rid(ctx))


def _quality(**ctx):
    from src.etl.quality import run_quality_checks
    run_quality_checks(_rid(ctx))


def _finish(**ctx):
    from src.pipeline import finish_run
    dag_run = ctx["dag_run"]
    failed = [t.task_id for t in dag_run.get_task_instances() if t.state == "failed"]
    finish_run(_rid(ctx), "FAILED" if failed else "SUCCESS", f"failed tasks: {failed}" if failed else None)
    if failed:
        raise RuntimeError(f"Upstream tasks failed: {failed}")


default_args = {
    "owner": "student-analytics",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="student_academic_analytics_pipeline",
    description="UCI ingestion -> staging -> validation/cleaning -> PostgreSQL star schema & marts -> DQ checks",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2026, 9, 1),
    catchup=False,
    max_active_runs=1,
    tags=["academic", "etl", "part1"],
) as dag:
    start = PythonOperator(task_id="start_run", python_callable=_start)
    ingest = PythonOperator(task_id="extract_uci_source", python_callable=_ingest)
    staging = PythonOperator(task_id="load_staging", python_callable=_staging)
    clean = PythonOperator(task_id="clean_and_validate", python_callable=_clean)
    analytics = PythonOperator(task_id="build_analytics_marts", python_callable=_analytics)
    quality = PythonOperator(task_id="data_quality_checks", python_callable=_quality, retries=0)
    finish = PythonOperator(task_id="finish_run", python_callable=_finish, trigger_rule=TriggerRule.ALL_DONE,
                            retries=0, outlets=[STUDENT_MART])

    start >> ingest >> staging >> clean >> analytics >> quality >> finish
