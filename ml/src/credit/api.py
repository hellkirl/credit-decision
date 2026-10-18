from __future__ import annotations

import json
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from sklearn.pipeline import Pipeline

from credit.config import CALIBRATOR_PATH, FEATURE_COLUMNS, METADATA_PATH, MODEL_PATH, REPORTS_DIR
from credit.model import load_model
import joblib
import numpy as np
from credit.schemas import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    CreditApplication,
    HealthResponse,
    MetricsResponse,
    PredictionResponse,
)

DEFAULT_THRESHOLD = 0.5
APPROVE_PD_THRESHOLD = 0.083
REJECT_PD_THRESHOLD = 0.285
GOOD_PROBABILITY_THRESHOLD = 1.0 - APPROVE_PD_THRESHOLD


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
    threshold: float = GOOD_PROBABILITY_THRESHOLD
    metadata: dict[str, Any] | None = None
    calibrator: Any = None


state = AppState()


@asynccontextmanager
async def lifespan(_: FastAPI):
    missing = [path for path in (MODEL_PATH, METADATA_PATH, CALIBRATOR_PATH) if not path.exists()]
    if missing:
        paths = ", ".join(str(path) for path in missing)
        raise RuntimeError(f"Required scoring artifacts are missing: {paths}. Run scripts/train.py")
    state.model = load_model()
    state.metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    state.calibrator = joblib.load(CALIBRATOR_PATH)
    # The Youden threshold remains diagnostic only and is not used for decisions.
    state.threshold = GOOD_PROBABILITY_THRESHOLD
    yield
    state.model = None
    state.metadata = None
    state.calibrator = None
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


def _validate_application(application: CreditApplication) -> list[dict[str, str]]:
    if state.metadata is None:
        raise HTTPException(status_code=503, detail="Scoring metadata is not loaded")

    reasons: list[dict[str, str]] = []
    values = application.model_dump()
    for field, bounds in state.metadata.get("numeric_ranges", {}).items():
        value = values.get(field)
        if value is None or value < bounds["min"] or value > bounds["max"]:
            reasons.append({"code": "NUMERIC_OUT_OF_RANGE", "field": field})

    for field, allowed in state.metadata.get("categorical_values", {}).items():
        value = values.get(field)
        if value is None or value not in allowed:
            reasons.append({"code": "UNSEEN_CATEGORY", "field": field})
    return reasons


def _calibrate_pd(proba_good: float) -> float:
    if state.calibrator is None:
        raise HTTPException(status_code=503, detail="PD calibrator is not loaded")
    pd_raw = float(np.clip(1.0 - proba_good, 1e-6, 1.0 - 1e-6))
    logit_pd = np.log(pd_raw / (1.0 - pd_raw))
    calibrated = float(state.calibrator.predict_proba(np.array([[logit_pd]]))[0, 1])
    return float(np.clip(calibrated, 0.0, 1.0))


def _predict_one(pd_value: float | None, age: int | None, reasons: list[dict[str, str]] | None = None) -> PredictionResponse:
    reasons = list(reasons or [])
    if pd_value is None:
        return PredictionResponse(
            credit_risk="bad",
            credit_risk_code=0,
            probability_good=None,
            probability_bad=None,
            threshold=GOOD_PROBABILITY_THRESHOLD,
            decision="manual_review",
            pd=None,
            reasons=reasons,
        )

    if pd_value < APPROVE_PD_THRESHOLD:
        decision = "approve"
    elif pd_value <= REJECT_PD_THRESHOLD:
        decision = "manual_review"
    else:
        decision = "reject"

    if decision == "reject" and age is not None and age <= 25:
        decision = "manual_review"
        reasons.append({"code": "YOUNG_APPLICANT_REVIEW", "field": "age"})

    good_probability = 1.0 - pd_value
    # Legacy binary fields remain for API compatibility; business decisions use decision/pd.
    good_code = int(pd_value <= REJECT_PD_THRESHOLD)
    return PredictionResponse(
        credit_risk="good" if good_code else "bad",
        credit_risk_code=good_code,
        probability_good=good_probability,
        probability_bad=pd_value,
        threshold=GOOD_PROBABILITY_THRESHOLD,
        decision=decision,
        pd=pd_value,
        reasons=reasons,
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
    invalid_reasons = _validate_application(application)
    if invalid_reasons:
        return _predict_one(None, application.age, invalid_reasons)
    X = _applications_to_frame([application])
    proba_good = float(state.model.predict_proba(X)[0, 1])
    pd_value = _calibrate_pd(proba_good)
    return _predict_one(pd_value, application.age)


@app.post(
    "/predict/batch",
    response_model=BatchPredictionResponse,
    tags=["scoring"],
    summary="Score multiple credit applications",
)
def predict_batch(payload: BatchPredictionRequest) -> BatchPredictionResponse:
    if state.model is None:
        raise HTTPException(status_code=503, detail="Model is not loaded")
    predictions = []
    for application in payload.applications:
        invalid_reasons = _validate_application(application)
        if invalid_reasons:
            predictions.append(_predict_one(None, application.age, invalid_reasons))
            continue
        X = _applications_to_frame([application])
        proba_good = float(state.model.predict_proba(X)[0, 1])
        predictions.append(_predict_one(_calibrate_pd(proba_good), application.age))
    return BatchPredictionResponse(predictions=predictions)
