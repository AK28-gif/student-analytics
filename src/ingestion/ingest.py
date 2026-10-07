"""Ingestion layer: UCI archive (HTTP) -> immutable raw copy in data/raw/<run_id>/.

For every source file we record extraction time, source, status, row count,
failed-row count and a SHA-256 checksum in audit.ingestion_log (+ a text log),
and malformed lines are captured into audit.rejected_records instead of
silently dropped.
"""
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common import config, db
from src.common.logging_utils import get_logger
from src.ingestion.uci import download_uci_archive, extract_subject_files

log = get_logger("ingest")
EXPECTED_COLUMNS = 33
SOURCE_NAME = "UCI Student Performance (id 320)"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text_log(line: str) -> None:
    config.EXTRACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(config.EXTRACTION_LOG, "a") as f:
        f.write(line + "\n")


def _record_ingestion(run_id, source_name, location, status, rows=None, failed=0, raw_path=None,
                      checksum=None, error=None):
    db.run(
        """INSERT INTO audit.ingestion_log (run_id, source_name, source_type, source_location, status,
               row_count, failed_row_count, raw_path, checksum_sha256, error_message)
           VALUES (:run_id, :source_name, 'http_zip', :loc, :status, :rows, :failed, :raw, :sha, :err)""",
        run_id=run_id, source_name=source_name, loc=location, status=status, rows=rows, failed=failed,
        raw=str(raw_path) if raw_path else None, sha=checksum, err=error,
    )
    _text_log(
        f"{datetime.now(timezone.utc).isoformat()} | run={run_id} | source={source_name} | status={status} "
        f"| rows={rows} | failed_rows={failed} | raw={raw_path} | error={error or '-'}"
    )


def _download_with_retry(url: str, attempts: int = 3) -> bytes:
    local_zip = os.getenv("UCI_LOCAL_ZIP")  # optional offline mode
    if local_zip:
        log.info("UCI_LOCAL_ZIP set - reading archive from %s", local_zip)
        return Path(local_zip).read_bytes()
    last = None
    for i in range(1, attempts + 1):
        try:
            return download_uci_archive(url)
        except Exception as exc:  # network errors, HTTP errors, timeouts
            last = exc
            log.warning("Download attempt %s/%s failed: %s", i, attempts, exc)
            time.sleep(2 * i)
    raise RuntimeError(f"Could not download {url} after {attempts} attempts: {last}")


def parse_source_file(path: Path):
    """Read a semicolon CSV, returning (dataframe, list_of_bad_lines)."""
    bad_lines = []

    def _on_bad(line):
        bad_lines.append(line)
        return None  # skip it, but keep it for the rejected-record log

    df = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False, na_values=[""],
                     engine="python", on_bad_lines=_on_bad)
    df.columns = [c.strip().lower() for c in df.columns]
    if len(df.columns) != EXPECTED_COLUMNS:
        raise ValueError(f"{path.name}: expected {EXPECTED_COLUMNS} columns, found {len(df.columns)}")
    return df, bad_lines


def run_ingestion(run_id: str) -> str:
    """Extract all sources for this run. Returns the path of the run manifest."""
    run_dir = config.RAW_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log.info("[%s] Ingesting %s from %s", run_id, SOURCE_NAME, config.UCI_DATASET_URL)

    try:
        archive = _download_with_retry(config.UCI_DATASET_URL)
        archive_path = run_dir / "student_performance.zip"
        archive_path.write_bytes(archive)          # untouched raw copy of what we received
        files = extract_subject_files(archive, run_dir)
    except Exception as exc:
        _record_ingestion(run_id, SOURCE_NAME, config.UCI_DATASET_URL, "FAILED", error=str(exc))
        raise

    manifest = {"run_id": run_id, "extracted_at": datetime.now(timezone.utc).isoformat(),
                "source": SOURCE_NAME, "url": config.UCI_DATASET_URL, "files": {}}
    for subject, path in files.items():
        name = f"{SOURCE_NAME} - {path.name}"
        try:
            df, bad = parse_source_file(path)
        except Exception as exc:
            _record_ingestion(run_id, name, config.UCI_DATASET_URL, "FAILED", raw_path=path, error=str(exc))
            raise
        for line in bad:
            db.run(
                """INSERT INTO audit.rejected_records (run_id, stage, source_name, rule_name, reason, record)
                   VALUES (:r, 'ingestion', :s, 'malformed_line', 'Wrong number of fields', CAST(:rec AS JSONB))""",
                r=run_id, s=path.name, rec=json.dumps({"line": line}),
            )
        checksum = _sha256(path)
        _record_ingestion(run_id, name, config.UCI_DATASET_URL, "SUCCESS", rows=len(df), failed=len(bad),
                          raw_path=path, checksum=checksum)
        manifest["files"][subject] = {"path": str(path), "rows": len(df), "failed_rows": len(bad),
                                      "sha256": checksum}
        log.info("[%s] %s: %s rows extracted, %s malformed lines", run_id, path.name, len(df), len(bad))

    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    (config.RAW_DIR / "LATEST").write_text(run_id)
    return str(manifest_path)
