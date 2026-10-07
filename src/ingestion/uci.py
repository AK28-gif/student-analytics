"""Download + unpack the UCI Student Performance dataset (id 320).

The official archive is a zip that contains a second zip (student.zip) holding
student-mat.csv and student-por.csv (semicolon separated)."""
import io
import urllib.request
import zipfile
from pathlib import Path

from src.common import config


def download_uci_archive(url: str = config.UCI_DATASET_URL, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "student-analytics-pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} while downloading {url}")
        return resp.read()


def extract_subject_files(archive: bytes, dest_dir: Path) -> dict:
    """Extract student-mat.csv / student-por.csv into dest_dir. Returns {subject_code: path}."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    wanted = {meta["uci_file"]: code for code, meta in config.SUBJECTS.items()}
    found = {}

    def _scan(zf: zipfile.ZipFile):
        for name in zf.namelist():
            base = Path(name).name
            if base in wanted:
                target = dest_dir / base
                target.write_bytes(zf.read(name))
                found[wanted[base]] = target
            elif base.endswith(".zip") and not base.startswith("."):
                _scan(zipfile.ZipFile(io.BytesIO(zf.read(name))))

    _scan(zipfile.ZipFile(io.BytesIO(archive)))
    missing = set(wanted.values()) - set(found)
    if missing:
        raise RuntimeError(f"UCI archive did not contain files for subjects: {missing}")
    return found
