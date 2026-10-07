# Student Performance & Dropout-Risk Prediction System - task runner
# Every target sources scripts/env.sh (venv, PYTHONPATH, AIRFLOW_HOME, PostgreSQL binaries).
SHELL := /bin/bash
ENV := source scripts/env.sh &&
PY := .venv/bin/python
AIRFLOW_VERSION := 2.10.5
AIRFLOW_CONSTRAINTS := https://raw.githubusercontent.com/apache/airflow/constraints-$(AIRFLOW_VERSION)/constraints-3.11.txt

.PHONY: help install tools venv docker-start docker-stop db-start db-stop db-setup init-db pipeline airflow-init airflow airflow-test \
        dashboard train score monitor monitor-drift monitor-api mlflow-ui api docker-build docker-up docker-down \
        docker-logs test dvc-repro demo clean

help:            ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' Makefile | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-15s\033[0m %s\n",$$1,$$2}'

install: tools venv db-start db-setup init-db airflow-init  ## one-time setup of everything

tools:           ## install PostgreSQL, Python 3.11, Docker/Colima (scripts/install_tools.sh)
	./scripts/install_tools.sh

venv:            ## create .venv and install Python packages (Airflow via official constraints)
	curl -sSfL -o .airflow-constraints.txt "$(AIRFLOW_CONSTRAINTS)"
	$(ENV) set -a; source .env; set +a; export UV_INDEX_URL="$${PIP_INDEX_URL:-https://pypi.org/simple}"; \
	uv venv --python 3.11 .venv && \
	VIRTUAL_ENV=.venv uv pip install "apache-airflow==$(AIRFLOW_VERSION)" -c .airflow-constraints.txt && \
	VIRTUAL_ENV=.venv uv pip install -r requirements.txt -c .airflow-constraints.txt
	rm -f .airflow-constraints.txt

docker-start:    ## start the Docker engine (Colima VM)
	$(ENV) colima start --vm-type vz --cpu 2 --memory 4 --disk 30

docker-stop:     ## stop the Docker engine
	$(ENV) colima stop

db-start:        ## start PostgreSQL 16 (background service)
	brew services start postgresql@16

db-stop:         ## stop PostgreSQL
	brew services stop postgresql@16

db-setup:        ## create DB role + database from .env
	./scripts/setup_database.sh

init-db:         ## create warehouse schemas & tables
	$(ENV) $(PY) -m src.pipeline --init-db

pipeline:        ## run the Part 1 pipeline end-to-end (without Airflow)
	$(ENV) $(PY) -m src.pipeline

airflow-init:    ## initialise the Airflow metadata DB + admin user (admin/admin)
	$(ENV) airflow db migrate && \
	airflow users create --username admin --password admin --firstname Admin --lastname User \
	  --role Admin --email admin@example.com || true

airflow:         ## start Airflow webserver (http://localhost:8080) + scheduler
	$(ENV) (airflow scheduler & airflow webserver --port 8080)

airflow-test:    ## execute both DAGs once from the CLI (no scheduler needed)
	$(ENV) airflow dags test student_academic_analytics_pipeline && \
	airflow dags test student_risk_ml_pipeline

dashboard:       ## Streamlit dashboard (http://localhost:8501)
	$(ENV) streamlit run dashboard/app.py

train:           ## train LR / RF / XGBoost, log to MLflow, register + export champion
	$(ENV) $(PY) -m src.ml.train

score:           ## batch-score all students into ml.risk_predictions
	$(ENV) $(PY) -m src.ml.predict

monitor:         ## drift / class-distribution / performance / API monitoring report
	$(ENV) $(PY) -m src.ml.monitor

monitor-drift:   ## monitoring demo on a simulated drifted cohort (shows retrain trigger)
	$(ENV) $(PY) -m src.ml.monitor --simulate-drift

monitor-api:     ## monitoring on the inputs received by the API
	$(ENV) $(PY) -m src.ml.monitor --source api

mlflow-ui:       ## MLflow UI (http://localhost:5001)
	$(ENV) $(PY) scripts/mlflow_ui.py

api:             ## FastAPI service locally (http://localhost:8000/docs)
	$(ENV) uvicorn api.main:app --port 8000 --reload

docker-build:    ## build the inference image
	$(ENV) docker compose build api

docker-up:       ## run the API container (http://localhost:8000/docs)
	$(ENV) docker compose up -d --build api

docker-down:
	$(ENV) docker compose down

docker-logs:
	$(ENV) docker compose logs -f api

test:            ## unit + API tests
	$(ENV) $(PY) -m pytest -q

dvc-repro:       ## reproduce the DVC pipeline (etl -> train), only stale stages
	$(ENV) dvc repro

demo: pipeline train score monitor  ## full end-to-end run without Airflow
