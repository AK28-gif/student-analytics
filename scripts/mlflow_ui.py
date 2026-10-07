"""MLflow UI without gunicorn (gunicorn workers segfault on some macOS setups).

    python scripts/mlflow_ui.py          -> http://localhost:5001
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("_MLFLOW_SERVER_FILE_STORE", f"sqlite:///{ROOT / 'mlflow.db'}")
os.environ.setdefault("_MLFLOW_SERVER_ARTIFACT_ROOT", str(ROOT / "mlruns"))
os.environ.setdefault("_MLFLOW_SERVER_SERVE_ARTIFACTS", "false")

from mlflow.server import app  # noqa: E402

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("MLFLOW_UI_PORT", "5001")), threaded=True)
