"""End-to-end Part 1 pipeline runner (the same functions are called by the Airflow DAG).

    python -m src.pipeline                 # full run: ingest -> staging -> clean -> analytics -> quality
    python -m src.pipeline --init-db       # (re)create schemas/tables only
"""
import argparse
from datetime import datetime, timezone

from sqlalchemy import text

from src.common import config, db
from src.common.logging_utils import get_logger
from src.etl.analytics import run_analytics
from src.etl.clean import run_clean
from src.etl.quality import run_quality_checks
from src.etl.staging import load_staging
from src.ingestion.ingest import run_ingestion

log = get_logger("pipeline")


def init_db() -> None:
    db.execute_sql_file(config.PROJECT_ROOT / "sql" / "schema.sql")
    log.info("Database schema ensured (%s@%s/%s)", config.DB_USER, config.DB_HOST, config.DB_NAME)


def start_run(triggered_by: str = "cli", run_id: str = None) -> str:
    init_db()
    run_id = run_id or datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
    db.run("""INSERT INTO audit.pipeline_runs (run_id, triggered_by) VALUES (:r, :t)
              ON CONFLICT (run_id) DO UPDATE SET status = 'RUNNING', started_at = now(), finished_at = NULL""",
           r=run_id, t=triggered_by)
    log.info("=== Pipeline run %s started (%s) ===", run_id, triggered_by)
    return run_id


def finish_run(run_id: str, status: str, message: str = None) -> None:
    db.run("UPDATE audit.pipeline_runs SET status = :s, finished_at = now(), message = :m WHERE run_id = :r",
           s=status, m=message, r=run_id)
    log.info("=== Pipeline run %s finished: %s %s ===", run_id, status, message or "")


def run_all(triggered_by: str = "cli") -> str:
    run_id = start_run(triggered_by)
    try:
        run_ingestion(run_id)
        load_staging(run_id)
        clean_stats = run_clean(run_id)
        run_analytics(run_id)
        run_quality_checks(run_id)
        finish_run(run_id, "SUCCESS", f"{clean_stats['enrollments']} enrolments, {clean_stats['rejected']} rejected")
    except Exception as exc:
        finish_run(run_id, "FAILED", str(exc)[:500])
        raise
    return run_id


def summary(run_id: str) -> None:
    with db.transaction() as conn:
        for label, sql in [
            ("ingestion", "SELECT source_name, status, row_count, failed_row_count FROM audit.ingestion_log WHERE run_id=:r"),
            ("rejected", "SELECT rule_name, count(*) FROM audit.rejected_records WHERE run_id=:r GROUP BY 1"),
            ("dq", "SELECT count(*) FILTER (WHERE passed), count(*) FROM audit.dq_results WHERE run_id=:r"),
        ]:
            for row in conn.execute(text(sql), {"r": run_id}):
                log.info("  %-10s %s", label, tuple(row))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--init-db", action="store_true", help="only create schemas/tables")
    args = p.parse_args()
    if args.init_db:
        init_db()
    else:
        rid = run_all()
        summary(rid)
