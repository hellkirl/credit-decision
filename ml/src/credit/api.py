from __future__ import annotations

import json
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from sklearn.pipeline import Pipeline

from credit.config import FEATURE_COLUMNS, MODEL_PATH, REPORTS_DIR
from credit.model import load_model
from credit.schemas import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    CreditApplication,
    HealthResponse,
    MetricsResponse,
    PredictionResponse,
)
DEFAULT_THRESHOLD = 0.5


@lru_cache(maxsize=1)
def _load_threshold() -> float:
    metrics_path = REPORTS_DIR / "metrics.json"
    if metrics_path.exists():
        data = json.loads(metrics_path.read_text())
        return float(data.get("threshold", DEFAULT_THRESHOLD))
    return DEFAULT_THRESHOLD


@lru_cache(maxsize=1)
def _load_metrics() -> dict[str, Any]:
    metrics_path = REPORTS_DIR / "metrics.json"
    if not metrics_path.exists():
        return {"threshold": _load_threshold()}
    return json.loads(metrics_path.read_text())


class AppState:
    model: Pipeline | None = None
    threshold: float = DEFAULT_THRESHOLD


state = AppState()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not MODEL_PATH.exists():
        raise RuntimeError(
            f"Model not found at {MODEL_PATH}. Run: PYTHONPATH=src python scripts/train.py"
        )
    state.model = load_model()
    state.threshold = _load_threshold()
    yield
    state.model = None
    _load_threshold.cache_clear()
    _load_metrics.cache_clear()


app = FastAPI(
    title="South German Credit Scoring API",
    description=(
        "Logistic regression credit-risk scorer trained on the "
        "South German Credit dataset. OpenAPI/Swagger UI is available at `/docs`."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


def _applications_to_frame(apps: list[CreditApplication]) -> pd.DataFrame:
    rows = [app.model_dump() for app in apps]
    return pd.DataFrame(rows)[FEATURE_COLUMNS]


def _predict_one(proba_good: float, threshold: float) -> PredictionResponse:
    code = int(proba_good >= threshold)
    return PredictionResponse(
        credit_risk="good" if code == 1 else "bad",
        credit_risk_code=code,
        probability_good=float(proba_good),
        probability_bad=float(1.0 - proba_good),
        threshold=threshold,
    )


@app.get("/", include_in_schema=False)
def root():
    return {
        "service": "South German Credit Scoring API",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@app.get("/health", response_model=HealthResponse, tags=["ops"])
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model_loaded=state.model is not None,
        threshold=state.threshold,
    )


@app.get("/metrics", response_model=MetricsResponse, tags=["ops"])
def metrics() -> MetricsResponse:
    data = _load_metrics()
    return MetricsResponse(
        threshold=float(data.get("threshold", state.threshold)),
        accuracy=data.get("accuracy"),
        precision=data.get("precision"),
        recall=data.get("recall"),
        f1=data.get("f1"),
        roc_auc=data.get("roc_auc"),
    )


@app.post(
    "/predict",
    response_model=PredictionResponse,
    tags=["scoring"],
    summary="Score one credit application",
)
def predict(application: CreditApplication) -> PredictionResponse:
    if state.model is None:
        raise HTTPException(status_code=503, detail="Model is not loaded")
    X = _applications_to_frame([application])
    proba_good = float(state.model.predict_proba(X)[0, 1])
    return _predict_one(proba_good, state.threshold)


@app.post(
    "/predict/batch",
    response_model=BatchPredictionResponse,
    tags=["scoring"],
    summary="Score multiple credit applications",
)
def predict_batch(payload: BatchPredictionRequest) -> BatchPredictionResponse:
    if state.model is None:
        raise HTTPException(status_code=503, detail="Model is not loaded")
    X = _applications_to_frame(payload.applications)
    probas = state.model.predict_proba(X)[:, 1]
    return BatchPredictionResponse(
        predictions=[_predict_one(float(p), state.threshold) for p in probas]
    )
