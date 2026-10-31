"""Compatibility exports for the verified per-disease environmental predictor."""

from app.services.verified_risk_predictor import (
    DISEASE_CLASSES,
    FEATURES,
    RiskModelUnavailable,
    has_any_model,
    has_model,
    model_artifact_path,
    predict_disease_presence,
)

__all__ = [
    "DISEASE_CLASSES",
    "FEATURES",
    "RiskModelUnavailable",
    "has_any_model",
    "has_model",
    "model_artifact_path",
    "predict_disease_presence",
]
