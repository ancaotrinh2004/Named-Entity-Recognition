# """
# PhoBERT Medical NER — FastAPI Backend
# Trung gian giữa UI và KServe: auth, error handling, response chuẩn JSON.
# """
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# from app.api.predict import router as predict_router
# from app.core.config import settings

# app = FastAPI(
#     title="PhoBERT Medical NER API",
#     description=(
#         "Backend nhận text tiếng Việt, validate API Key, "
#         "gọi KServe PhoBERT model, trả về medical profile JSON."
#     ),
#     version="1.0.0",
#     docs_url="/docs",
#     redoc_url="/redoc",
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.get_cors_origins(),
#     allow_methods=["POST", "GET", "OPTIONS"],
#     allow_headers=["X-API-Key", "Content-Type"],
# )

# app.include_router(predict_router, prefix="/predict", tags=["Predict"])


# @app.get("/healthz", tags=["Health"])
# async def health():
#     return {"status": "ok", "version": "1.0.0"}

"""
PhoBERT Medical NER — FastAPI Backend
Trung gian giữa UI và KServe: auth, error handling, response chuẩn JSON.
Metrics: OpenTelemetry + Prometheus (counter, histogram cho latency)
"""
from time import time
from functools import wraps

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from prometheus_client import start_http_server
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from app.api.predict import router as predict_router
from app.core.config import settings

# ── Prometheus metrics setup ────────────────────────────
# Expose metrics tại port 8099 (tách riêng khỏi app port 8000)
start_http_server(port=8099, addr="0.0.0.0")

resource = Resource(attributes={SERVICE_NAME: "phobert-backend"})
reader = PrometheusMetricReader()
provider = MeterProvider(resource=resource, metric_readers=[reader])
set_meter_provider(provider)
meter = metrics.get_meter("phobert-backend", "1.0.0")

# Counter — đếm số request
request_counter = meter.create_counter(
    name="phobert_request_counter",
    description="Total number of prediction requests",
)

# Histogram — đo latency
latency_histogram = meter.create_histogram(
    name="phobert_request_latency",
    description="Prediction request latency",
    unit="seconds",
)

# ── Metrics decorator ───────────────────────────────────
def track_metrics(endpoint: str):
    """Decorator đo latency và đếm request cho từng endpoint."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time()
            result = await func(*args, **kwargs)
            elapsed = time() - start

            label = {"api": endpoint}
            request_counter.add(1, label)
            latency_histogram.record(elapsed, label)

            logger.info(f"[{endpoint}] latency={elapsed:.3f}s")
            return result
        return wrapper
    return decorator


# ── FastAPI app ─────────────────────────────────────────
app = FastAPI(
    title="PhoBERT Medical NER API",
    description=(
        "Backend nhận text tiếng Việt, validate API Key, "
        "gọi KServe PhoBERT model, trả về medical profile JSON."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type"],
)

app.include_router(predict_router, prefix="/predict", tags=["Predict"])


@app.get("/healthz", tags=["Health"])
async def health():
    return {"status": "ok", "version": "1.0.0"}