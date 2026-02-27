FROM python:3.9-slim

WORKDIR /app

# System deps:
# - curl: healthcheck
# - git: một số package cần khi install từ source
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# Copy và install dependencies production (KHÔNG có pytest)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# KServe predictor lắng nghe port 8080
EXPOSE 8080

# Biến môi trường mặc định — override qua InferenceService env
ENV MODEL_NAME=phobert-medical \
    MODEL_VERSION=latest \
    MLFLOW_TRACKING_URI=http://mlflow.mlops.svc.cluster.local:5000 \
    MLFLOW_S3_ENDPOINT_URL=http://minio.mlops.svc.cluster.local:9000 \
    MLFLOW_S3_IGNORE_TLS=true

# ✅ Dùng -m app.model để Python nhận diện đúng package
ENTRYPOINT ["python", "-m", "app.model"]