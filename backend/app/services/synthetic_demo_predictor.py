"""Inference helpers for isolated synthetic environmental pipeline demonstrations."""

import base64
import json
from functools import lru_cache
from pathlib import Path

FEATURES = (
    "soil_ph",
    "temperature_c",
    "relative_humidity_pct",
    "rainfall_mm",
    "wind_speed_kmh",
    "dew_point_c",
)
FUSION_DISEASES = ("Mosaic", "RedRot", "Rust", "Yellow")
UNFUSED_DISEASES = ("Wilt",)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEMO_ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "environmental_demo"


class SyntheticDemoUnavailable(Exception):
    pass


def _validate_demo_artifacts(artifact_dir: Path) -> None:
    report_path = artifact_dir / "SYNTHETIC_DEMO_ONLY_report.json"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyntheticDemoUnavailable("Synthetic demo report is missing or invalid.") from exc

    if (
        not isinstance(report, dict)
        or report.get("real_world_validity") is not False
        or report.get("safe_for_api_prediction") is not False
        or report.get("target_column") != "synthetic_target"
        or "SYNTHETIC" not in str(report.get("warning", "")).upper()
    ):
        raise SyntheticDemoUnavailable("Environmental artifacts are not marked as synthetic-demo-only.")


@lru_cache(maxsize=5)
def _load_model(artifact_path: str):
    try:
        import xgboost as xgb
    except ImportError as exc:
        raise SyntheticDemoUnavailable("Install the optional ML dependencies to use the synthetic demo.") from exc

    model = xgb.XGBClassifier()
    try:
        model.load_model(artifact_path)
    except (OSError, ValueError, xgb.core.XGBoostError) as exc:
        raise SyntheticDemoUnavailable("A synthetic environmental demo model could not be loaded.") from exc
    return model


def _predict_one(disease: str, values: dict[str, float | None], artifact_dir: Path) -> dict:
    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        raise SyntheticDemoUnavailable("Install the optional ML dependencies to use the synthetic demo.") from exc

    slug = disease.lower()
    artifact = artifact_dir / f"demo_xgboost_{slug}.json"
    if not artifact.is_file():
        raise SyntheticDemoUnavailable(f"Synthetic demo model for {disease} is missing.")

    row = {feature: np.nan if values[feature] is None else values[feature] for feature in FEATURES}
    frame = pd.DataFrame([row], columns=FEATURES)
    model = _load_model(str(artifact.resolve()))
    classes = list(model.classes_)
    if 1 not in classes:
        raise SyntheticDemoUnavailable(f"Synthetic demo model for {disease} has an invalid target class.")

    score = float(model.predict_proba(frame)[0][classes.index(1)])
    return {"disease_class": disease, "synthetic_environment_score": round(score, 5)}


def run_synthetic_fusion_demo(
    image_class_scores: dict[str, float],
    feature_values: dict[str, float | None],
    artifact_dir: Path = DEMO_ARTIFACT_DIR,
) -> dict:
    _validate_demo_artifacts(artifact_dir)
    missing = [feature for feature in FEATURES if feature not in feature_values]
    if missing:
        raise ValueError(f"Missing demo features: {', '.join(missing)}")
    invalid_scores = [
        disease for disease in FUSION_DISEASES
        if disease not in image_class_scores
        or not 0 <= float(image_class_scores[disease]) <= 1
    ]
    if invalid_scores:
        raise ValueError(f"Missing or invalid image scores for: {', '.join(invalid_scores)}")
    missing_weather = [feature for feature in FEATURES[1:] if feature_values[feature] is None]
    if missing_weather:
        raise ValueError(f"Current weather is missing demo features: {', '.join(missing_weather)}")

    scores = []
    for disease in FUSION_DISEASES:
        environmental = _predict_one(disease, feature_values, artifact_dir)
        image_score = float(image_class_scores.get(disease, 0.0))
        environmental_score = environmental["synthetic_environment_score"]
        scores.append({
            "disease_class": disease,
            "image_score": round(image_score, 5),
            **environmental,
            "demo_fusion_score": round((image_score + environmental_score) / 2, 5),
        })
    scores.sort(key=lambda result: result["demo_fusion_score"], reverse=True)
    selected_disease = scores[0]["disease_class"]

    try:
        import shap

        model_path = (artifact_dir / f"demo_xgboost_{selected_disease.lower()}.json").resolve()
        model = _load_model(str(model_path))
        import numpy as np
        import pandas as pd

        row = {feature: np.nan if feature_values[feature] is None else feature_values[feature] for feature in FEATURES}
        frame = pd.DataFrame([row], columns=FEATURES)
        shap_values = shap.TreeExplainer(model)(frame).values
        if shap_values.ndim == 3:
            classes = list(model.classes_)
            shap_values = shap_values[:, :, classes.index(1)]
        contributions = shap_values[0]
    except (ImportError, ValueError, TypeError, IndexError) as exc:
        raise SyntheticDemoUnavailable("SHAP could not explain the synthetic demo model.") from exc

    drivers = [
        {
            "feature": feature,
            "value": None if feature_values[feature] is None else round(float(feature_values[feature]), 3),
            "shap_value": round(float(contribution), 5),
            "effect": "increases_demo_score" if contribution > 0 else "decreases_demo_score",
        }
        for feature, contribution in zip(FEATURES, contributions)
    ]
    drivers.sort(key=lambda item: abs(item["shap_value"]), reverse=True)

    ale_path = artifact_dir / f"SYNTHETIC_DEMO_ONLY_ale_{selected_disease.lower()}.png"
    try:
        ale_image = base64.b64encode(ale_path.read_bytes()).decode("ascii")
    except OSError as exc:
        raise SyntheticDemoUnavailable("The precomputed synthetic ALE plot is missing.") from exc

    return {
        "status": "synthetic_demo_only",
        "synthetic_demo_only": True,
        "ranked_scores": scores,
        "not_fused_classes": {
            disease: "The image classifier has no matching class; late fusion is not computed for this disease."
            for disease in UNFUSED_DISEASES
        },
        "explanation_disease": selected_disease,
        "shap_drivers": drivers[:5],
        "ale_plot_base64": ale_image,
        "warning": (
            "Synthetic demo only. Environmental labels are arbitrary program-generated values; "
            "the fusion score is not a disease risk, diagnosis, forecast, or agronomic recommendation."
        ),
    }
