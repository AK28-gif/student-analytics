# Student Performance & Dropout-Risk Prediction System

An end-to-end data engineering + MLOps project built on the public **UCI Student Performance** dataset.

- **Part 1 – Data pipeline:** download → raw copy → staging → validation & cleaning → PostgreSQL star schema → data marts → Streamlit dashboard, orchestrated by **Apache Airflow**.
- **Part 2 – MLOps:** predict which students will **fail** a subject (final grade < 10/20) using Logistic Regression, Random Forest and XGBoost. Includes **MLflow** tracking and model registry, **DVC** versioning, a **FastAPI** service in **Docker**, and drift monitoring with automatic retraining.

![Architecture](docs/architecture.svg)

| Technology | Used for | Where |
|---|---|---|
| Python + Pandas | ingestion, cleaning, transforms | `src/ingestion`, `src/etl` |
| Apache Airflow 2.10 | scheduling / orchestration | `dags/` |
| PostgreSQL 16 | data warehouse | `sql/schema.sql` |
| Streamlit + Plotly | dashboard (7 pages) | `dashboard/` |
| scikit-learn, XGBoost | models | `src/ml/train.py` |
| MLflow | experiment tracking + model registry | `mlflow.db`, `mlruns/` |
| DVC | dataset & model versioning | `dvc.yaml`, `dvc.lock` |
| FastAPI | prediction API | `api/main.py` |
| Docker (Colima) | containerised API | `api/Dockerfile`, `docker-compose.yml` |

---

## 1. Running it again later (everything is already installed on this Mac)

Open a terminal in the project folder and run these steps in order:

```bash
cd ~/work/student-analytics

# 1) start the database and the Docker engine (once after each reboot)
make db-start          # PostgreSQL
make docker-start      # Docker engine (Colima). Only needed for the API container

# 2) run the data pipeline (download -> clean -> warehouse)
make pipeline

# 3) train the models (MLflow) and score all students
make train
make score
make monitor

# 4) start the prediction API in Docker
make docker-up         # http://localhost:8000/docs

# 5) open the dashboard
make dashboard         # http://localhost:8501
```

Shortcut: `make demo` runs steps 2 and 3 together (pipeline → train → score → monitor).

### The web UIs (each in its own terminal)

| Command | URL | Login |
|---|---|---|
| `make dashboard` | http://localhost:8501 | – |
| `make airflow` | http://localhost:8080 | admin / admin |
| `make mlflow-ui` | http://localhost:5001 | – |
| `make api` (local) or `make docker-up` (Docker) | http://localhost:8000/docs | – |

Stop everything with `Ctrl+C` in those terminals, then run `make docker-down`, `make docker-stop` and `make db-stop`.

---

## 2. Running with Airflow (the orchestrated way)

```bash
make airflow           # starts scheduler + web UI at http://localhost:8080 (admin / admin)
```

In the UI, switch on and trigger **`student_academic_analytics_pipeline`**. It runs these tasks in order:

`start_run → extract_uci_source → load_staging → clean_and_validate → build_analytics_marts → data_quality_checks → finish_run`

When it succeeds, it automatically triggers **`student_risk_ml_pipeline`** (via an Airflow Dataset):

`monitor_drift → train_and_register → batch_score`

The ML DAG retrains the models and registers a new MLflow model version on **every** run. The drift report is saved first, so you can compare each new dataset with the previous model's training data.

To run both DAGs once without the scheduler:

```bash
make airflow-test
```

---

## 3. All `make` commands

```
make help            list every command
make pipeline        Part 1 pipeline end-to-end (no Airflow)
make train           train 3 models, log to MLflow, register the best as "champion"
make score           write predictions for every student to ml.risk_predictions
make monitor         drift / accuracy / API report (reports/monitoring/latest.html)
make monitor-drift   same report on a simulated "drifted" cohort (shows the retrain trigger)
make monitor-api     monitoring based on the requests the API received
make dvc-repro       re-run the DVC pipeline (only the stages whose inputs changed)
make test            unit tests + API tests
make docker-up       build + run the API container   (make docker-logs / make docker-down)
```

---

## 4. First-time setup on a NEW machine (macOS, Apple Silicon)

You only need this to install the project on another computer.

```bash
# prerequisites: Homebrew (https://brew.sh) and git
cp .env.example .env          # then edit DB_PASSWORD (and PIP_INDEX_URL if PyPI is blocked)
make install                  # installs tools, creates .venv, creates the database, initialises Airflow
```

`make install` runs these steps:
1. `make tools` installs PostgreSQL 16 (Homebrew), Python 3.11 (`uv`), and the Docker CLI + Colima (prebuilt binaries in `~/.local/bin`).
2. `make venv` creates `.venv` and installs Airflow 2.10.5 with its official constraints, plus `requirements.txt`. Exact tested versions are in `requirements-lock.txt`.
3. `make db-start db-setup init-db` starts PostgreSQL, creates the role and database from `.env`, and creates all schemas and tables.
4. `make airflow-init` sets up the Airflow metadata DB and the `admin`/`admin` user.

Then follow section 1.

> **Note for this network:** `files.pythonhosted.org` is blocked, so `.env` sets `PIP_INDEX_URL` to the package mirror. Both `make venv` and the Docker build use it.

---

## 5. Project structure

```
student-analytics/
├── dags/                      Airflow DAGs (Part 1 pipeline, Part 2 ML pipeline)
├── src/
│   ├── common/                config (.env), DB connection, student-id standardisation
│   ├── ingestion/             download UCI zip, raw copy, ingestion log
│   ├── etl/                   staging, validation rules, cleaning, star schema + marts, DQ checks
│   ├── ml/                    features, training (MLflow), batch scoring, monitoring
│   └── pipeline.py            runs the whole Part 1 pipeline
├── sql/schema.sql             all PostgreSQL schemas & tables
├── dashboard/                 Streamlit app (app.py + pages/)
├── api/                       FastAPI service + Dockerfile
├── tests/                     pytest tests
├── params.yaml                ML + monitoring parameters (tracked by DVC)
├── dvc.yaml / dvc.lock        DVC pipeline + data/model hashes
├── docs/                      architecture, data dictionary, dataset info, report, evidence
├── data/raw/<run_id>/         raw copy of every download (immutable)
├── data/processed/            feature snapshot (DVC-tracked)
├── models/champion/           exported best model (DVC-tracked, used by the API)
└── reports/                   metrics, confusion matrices, monitoring reports
```

## 6. Data layers

| Layer | Where | What |
|---|---|---|
| Raw | `data/raw/<run_id>/` | downloaded zip + CSVs + `manifest.json` (rows, SHA-256) |
| Staging | `staging.stg_uci_student` | rows as landed (TEXT) + source file / line / run id |
| Cleaned | `clean.student`, `clean.enrollment` | typed, validated, de-duplicated, standard `STU00001` ids |
| Analytical | `analytics.*` | `dim_student`, `dim_subject`, `dim_term`, `fact_student_term`, `fact_enrollment` + marts |
| Audit | `audit.*` | `pipeline_runs`, `ingestion_log`, `rejected_records`, `dq_results` |
| ML | `ml.*` | `risk_predictions`, `monitoring_reports` |

Rejected records are also written to `logs/rejected_records.log`. The extraction log is `logs/extraction_audit.log`.

## 7. Documentation

- [docs/architecture.svg](docs/architecture.svg) – architecture diagram
- [docs/data_dictionary.md](docs/data_dictionary.md) – every table and column, validation rules, formulas
- [docs/dataset_sources.md](docs/dataset_sources.md) – dataset source, licence, access instructions
- [docs/REPORT.md](docs/REPORT.md) – project report
- [docs/evidence/](docs/evidence/) – screenshots and execution logs

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `could not connect to server` | `make db-start` |
| `Cannot connect to the Docker daemon` | `make docker-start` |
| Dashboard says "no trained model" | `make train && make score` |
| Risk Prediction page says API offline | `make docker-up` (or `make api`) |
| API still serves an old model after retraining | `make docker-up` rebuilds the image with the new champion |
| `pip install` fails with SSL / connection errors | set `PIP_INDEX_URL` in `.env` to your package mirror |
| `mlflow ui` workers crash (SIGSEGV) on macOS | use `make mlflow-ui`, which runs a non-forking server |

Dataset: P. Cortez and A. Silva, *Using Data Mining to Predict Secondary School Student Performance*, FUBUTEC 2008. UCI ML Repository, CC BY 4.0.
