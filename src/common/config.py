"""Central configuration. All credentials come from environment variables (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

# --- Database (PostgreSQL warehouse) ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "student_db")
DB_USER = os.getenv("DB_USER", "student_app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# --- Data sources ---
UCI_DATASET_URL = os.getenv(
    "UCI_DATASET_URL",
    "https://archive.ics.uci.edu/static/public/320/student+performance.zip",
)

# --- Data layers on disk ---
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FEATURES_FILE = PROCESSED_DIR / "student_features.csv"
LOG_DIR = PROJECT_ROOT / "logs"
REJECTED_LOG = LOG_DIR / "rejected_records.log"
EXTRACTION_LOG = LOG_DIR / "extraction_audit.log"

# --- ML ---
MODELS_DIR = PROJECT_ROOT / "models"
CHAMPION_DIR = MODELS_DIR / "champion"
REPORTS_DIR = PROJECT_ROOT / "reports"
PARAMS_FILE = PROJECT_ROOT / "params.yaml"
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", f"sqlite:///{PROJECT_ROOT / 'mlflow.db'}")
MLFLOW_EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "student-risk-prediction")
REGISTERED_MODEL_NAME = os.getenv("REGISTERED_MODEL_NAME", "student-risk-classifier")
API_URL = os.getenv("API_URL", "http://localhost:8000")
PREDICTION_LOG = Path(os.getenv("PREDICTION_LOG", str(LOG_DIR / "api" / "predictions.jsonl")))

# Domain constants
PASS_MARK = 10          # UCI grades are on a 0-20 scale; >= 10 is a pass
MAX_GRADE = 20
SUBJECTS = {
    "MAT": {"subject_name": "Mathematics", "department": "Science & Mathematics", "uci_file": "student-mat.csv"},
    "POR": {"subject_name": "Portuguese Language", "department": "Languages & Humanities", "uci_file": "student-por.csv"},
}
# UCI grades G1, G2, G3 = first period, second period, final grade -> three assessment terms
TERMS = {"P1": ("Period 1", 1, "g1"), "P2": ("Period 2", 2, "g2"), "P3": ("Final", 3, "g3")}
# UCI "absences" is a yearly count of missed classes per subject. Attendance % assumes this
# many scheduled sessions per subject per school year (documented assumption, see data dictionary).
SESSIONS_PER_YEAR = int(os.getenv("SESSIONS_PER_YEAR", "120"))
