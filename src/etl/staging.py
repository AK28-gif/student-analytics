"""Staging layer: load raw files into PostgreSQL exactly as landed (all TEXT) + lineage."""
import json
from pathlib import Path

from src.common import config, db
from src.common.logging_utils import get_logger
from src.ingestion.ingest import parse_source_file

log = get_logger("staging")
STAGING_TABLE = "staging.stg_uci_student"


def load_staging(run_id: str) -> int:
    manifest = json.loads((config.RAW_DIR / run_id / "manifest.json").read_text())
    total = 0
    with db.transaction() as conn:
        db.truncate(conn, STAGING_TABLE)
        for subject, meta in manifest["files"].items():
            df, _ = parse_source_file(Path(meta["path"]))
            df.insert(0, "subject_code", subject)
            df.insert(0, "source_row", range(2, len(df) + 2))  # line number in the CSV (header = 1)
            df.insert(0, "source_file", Path(meta["path"]).name)
            df["_run_id"] = run_id
            df.to_sql("stg_uci_student", conn, schema="staging", if_exists="append", index=False,
                      method="multi", chunksize=1000)
            total += len(df)
            log.info("[%s] staged %s rows from %s", run_id, len(df), meta["path"])
    return total
