"""Inference adapter for per-disease models produced by train_risk_model.py."""

import re
from pathlib import Path
from time import perf_counter

FEATURES = [
    "soil_ph",
    "temperature_c",
    "relative_humidity_pct",
    "rainfall_mm",
    "wind_speed_kmh",
    "dew_point_c",
]
DISEASE_CLASSES = ("Mosaic", "RedRot", "Rust", "Yellow", "Wilt")


class RiskModelUnavailable(Exception):
    pass


def model_artifact_path(configured_path: str, disease_class: str) -> Path:
    if disease_class not in DISEASE_CLASSES:
        raise ValueError(f"Unsupported disease class: {disease_class}")
    configured = Path(configured_path)
    artifact_dir = configured if configured.suffix == "" else configured.parent
    slug = re.sub(r"[^a-z0-9_-]+", "_", disease_class.lower()).strip("_")
    return artifact_dir / f"xgboost_{slug}.json"


def has_any_model(configured_path: str) -> bool:
    return any(has_model(configured_path, disease) for disease in DISEASE_CLASSES)


def has_model(configured_path: str, disease_class: str) -> bool:
    return model_artifact_path(configured_path, disease_class).is_file()


def predict_disease_presence(
    disease_class: str,
    feature_values: dict[str, float | None],
    configured_path: str,
) -> dict:
    started = perf_counter()
    artifact = model_artifact_path(configured_path, disease_class)
    if not artifact.is_file():
        raise RiskModelUnavailable(
            f"No trained environmental model is available for {disease_class}. "
            "Train it from expert-verified, consented field observations first."
        )

    missing = [feature for feature in FEATURES if feature not in feature_values]
    if missing:
        raise ValueError(f"Missing model features: {', '.join(missing)}")
    missing_weather = [feature for feature in FEATURES[1:] if feature_values[feature] is None]
    if missing_weather:
        raise ValueError(f"Current weather is missing model features: {', '.join(missing_weather)}")

    try:
        import numpy as np
        import pandas as pd
        import shap
        import xgboost as xgb
    except ImportError as exc:
        raise RiskModelUnavailable(
            "Install the optional risk-model dependencies before using environmental assessment."
        ) from exc

    model = xgb.XGBClassifier()
    try:
        model.load_model(str(artifact))
    except (ValueError, xgb.core.XGBoostError) as exc:
        raise RiskModelUnavailable(f"The environmental model artifact is invalid: {artifact.name}") from exc

    row = {feature: np.nan if feature_values[feature] is None else feature_values[feature] for feature in FEATURES}
    frame = pd.DataFrame([row], columns=FEATURES)
    probabilities = model.predict_proba(frame)[0]
    classes = list(model.classes_)
    if 1 not in classes:
        raise RiskModelUnavailable("The model artifact does not contain the positive disease-presence class.")
    score = float(probabilities[classes.index(1)])

    try:
        shap_values = shap.TreeExplainer(model)(frame).values
        if shap_values.ndim == 3:
            shap_values = shap_values[:, :, classes.index(1)]
        contributions = shap_values[0]
    except (ValueError, TypeError, IndexError) as exc:
        raise RiskModelUnavailable("SHAP could not explain this model artifact.") from exc

    drivers = [
        {
            "feature": feature,
            "value": None if feature_values[feature] is None else round(float(feature_values[feature]), 3),
            "shap_value": round(float(contribution), 5),
            "effect": "increases_score" if contribution > 0 else "decreases_score",
        }
        for feature, contribution in zip(FEATURES, contributions)
    ]
    drivers.sort(key=lambda item: abs(item["shap_value"]), reverse=True)

    return {
        "status": "experimental_observation_time_association",
        "disease_class": disease_class,
        "disease_presence_score": round(score, 5),
        "score_note": "Uncalibrated model score for disease presence at observation time; not a future forecast or diagnosis.",
        "primary_drivers": drivers[:5],
        "input_features": row,
        "model_version": artifact.stem,
        "processing_time_ms": round((perf_counter() - started) * 1000),
        "scientific_disclosure": (
            "This experimental score is learned from expert-verified, consented observations "
            "at the time weather was recorded. It is not a calibrated probability, future "
            "disease forecast, or confirmed diagnosis."
        ),
    }
