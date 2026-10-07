# Inference image for the student fail-risk model (FastAPI + scikit-learn/XGBoost)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MODEL_DIR=/app/models/champion PREDICTION_LOG=/app/logs/api/predictions.jsonl
# libgomp1 = OpenMP runtime required by XGBoost
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# Override with a mirror if PyPI is blocked on your network (set PIP_INDEX_URL in .env)
ARG PIP_INDEX_URL=https://pypi.org/simple
COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir --index-url "$PIP_INDEX_URL" -r api/requirements.txt

# Only the code the service needs + the exported champion model (immutable artifact)
COPY src/__init__.py src/__init__.py
COPY src/ml/__init__.py src/ml/features.py src/ml/
COPY api/__init__.py api/main.py api/
COPY models/champion models/champion

RUN useradd --create-home appuser && mkdir -p /app/logs/api && chown -R appuser /app/logs
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD curl -fs http://localhost:8000/health || exit 1
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
