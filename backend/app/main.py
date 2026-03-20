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
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.predict import router as predict_router
from app.core.config import settings

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


# ── Prometheus metrics ──────────────────────────────────
# Expose /metrics endpoint cho Prometheus scrape
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/healthz", "/docs", "/redoc", "/openapi.json"],
    inprogress_name="fastapi_inprogress",
    inprogress_labels=True,
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)