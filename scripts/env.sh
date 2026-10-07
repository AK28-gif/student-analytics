# Source this file to get the project environment:  source scripts/env.sh
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-${(%):-%x}}")/.." && pwd)"
export PROJECT_ROOT
export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export AIRFLOW_HOME="$PROJECT_ROOT/airflow_home"
export AIRFLOW__CORE__DAGS_FOLDER="$PROJECT_ROOT/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__WEBSERVER__EXPOSE_CONFIG=False
export AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL=30
# macOS: avoid fork-safety crashes in Airflow task processes
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export NO_PROXY="*"
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PROJECT_ROOT/.venv/bin:$HOME/.local/bin:$PATH"
export MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR=false
# libpq: skip the Kerberos/GSS probe that hangs in forked processes on macOS
export PGGSSENCMODE=disable
