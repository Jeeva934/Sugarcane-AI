"""Train per-disease environmental models from verified, consented field observations."""

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

FEATURES = [
    "soil_ph",
    "temperature_c",
    "relative_humidity_pct",
    "rainfall_mm",
    "wind_speed_kmh",
    "dew_point_c",
]
WEATHER_FEATURES = [feature for feature in FEATURES if feature != "soil_ph"]
REQUIRED_COLUMNS = {
    "date",
    "farm_group",
    "disease_class",
    "outcome",
    "verification_status",
    "research_consent",
    *FEATURES,
}
MIN_CLASS_SAMPLES_PER_SPLIT = 10


class PositiveProbabilityModel:
    def __init__(self, model):
        self.model = model

    def predict(self, features):
        return self.model.predict_proba(features)[:, 1]


def load_training_data(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing)}")
    if not frame["verification_status"].eq("verified").all():
        raise ValueError("Training input must contain only expert-verified observations.")
    if not frame["research_consent"].astype(str).str.lower().isin({"true", "1"}).all():
        raise ValueError("Every training row must have explicit research consent.")

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["outcome"] = frame["outcome"].str.lower()
    if frame["date"].isna().any():
        raise ValueError("Every record must have a valid date.")
    if not frame["outcome"].isin({"present", "absent"}).all():
        raise ValueError("Outcome must be expert-reviewed present or absent.")
    if frame["farm_group"].isna().any() or frame["disease_class"].isna().any():
        raise ValueError("Every row requires a farm group and disease class.")
    for column in FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=WEATHER_FEATURES)
    if frame.empty:
        raise ValueError("No complete weather and soil records remain after validation.")
    return frame


def chronological_split(frame: pd.DataFrame):
    dates = np.array(sorted(frame["date"].dt.normalize().unique()))
    if len(dates) < 10:
        raise ValueError("At least 10 distinct observation dates are required for chronological validation.")
    train_end = max(1, int(len(dates) * 0.6))
    validation_end = max(train_end + 1, int(len(dates) * 0.8))
    validation_end = min(validation_end, len(dates) - 1)
    train_dates = set(dates[:train_end])
    validation_dates = set(dates[train_end:validation_end])
    test_dates = set(dates[validation_end:])
    normalized = frame["date"].dt.normalize()
    return (
        frame[normalized.isin(train_dates)],
        frame[normalized.isin(validation_dates)],
        frame[normalized.isin(test_dates)],
    )


def require_class_balance(frame: pd.DataFrame, disease: str, split_name: str) -> None:
    counts = frame["target"].value_counts()
    if any(counts.get(label, 0) < MIN_CLASS_SAMPLES_PER_SPLIT for label in (0, 1)):
        raise ValueError(
            f"{disease}: {split_name} needs at least {MIN_CLASS_SAMPLES_PER_SPLIT} verified "
            f"present and {MIN_CLASS_SAMPLES_PER_SPLIT} verified absent labels; "
            f"found absent={counts.get(0, 0)}, present={counts.get(1, 0)}."
        )


def train_disease_model(frame: pd.DataFrame, disease: str, output_dir: Path) -> dict:
    from sklearn.metrics import accuracy_score, average_precision_score, brier_score_loss, roc_auc_score
    from xgboost import XGBClassifier

    disease_rows = frame[frame["disease_class"] == disease].copy()
    disease_rows["target"] = disease_rows["outcome"].map({"absent": 0, "present": 1})
    train, validation, test = chronological_split(disease_rows)
    for subset, name in ((train, "train"), (validation, "validation"), (test, "test")):
        require_class_balance(subset, disease, name)

    candidates = [
        {"max_depth": depth, "n_estimators": estimators, "learning_rate": rate}
        for depth in (2, 3)
        for estimators in (50, 100)
        for rate in (0.03, 0.08)
    ]
    best_model = None
    best_params = None
    best_auc = -1.0
    for params in candidates:
        candidate = XGBClassifier(
            **params,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=42,
            n_jobs=2,
        )
        candidate.fit(train[FEATURES], train["target"])
        probabilities = candidate.predict_proba(validation[FEATURES])[:, 1]
        score = roc_auc_score(validation["target"], probabilities)
        if score > best_auc:
            best_auc = score
            best_model = candidate
            best_params = params
    if best_model is None:
        raise RuntimeError(f"No candidate model could be selected for {disease}.")

    final_model = XGBClassifier(
        **best_params,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42,
        n_jobs=2,
    )
    train_validation = pd.concat([train, validation]).sort_values("date")
    final_model.fit(train_validation[FEATURES], train_validation["target"])
    test_probabilities = final_model.predict_proba(test[FEATURES])[:, 1]
    metrics = {
        "test_records": int(len(test)),
        "accuracy_at_0_5": round(float(accuracy_score(test["target"], test_probabilities >= 0.5)), 4),
        "auroc": round(float(roc_auc_score(test["target"], test_probabilities)), 4),
        "auprc": round(float(average_precision_score(test["target"], test_probabilities)), 4),
        "brier_score": round(float(brier_score_loss(test["target"], test_probabilities)), 4),
        "test_start": test["date"].min().date().isoformat(),
        "test_end": test["date"].max().date().isoformat(),
    }

    safe_name = re.sub(r"[^a-z0-9_-]+", "_", disease.lower()).strip("_")
    artifact_path = output_dir / f"xgboost_{safe_name}.json"
    final_model.save_model(artifact_path)

    import shap

    explainer = shap.TreeExplainer(final_model)
    shap_values = explainer.shap_values(test[FEATURES])
    global_importance = {
        feature: round(float(value), 6)
        for feature, value in zip(FEATURES, np.abs(shap_values).mean(axis=0))
    }
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PyALE import ale

    ale_model = PositiveProbabilityModel(final_model)
    ale_plot, axes = plt.subplots(2, 3, figsize=(14, 8))
    for axis, feature in zip(axes.flat, FEATURES):
        if train_validation[feature].nunique(dropna=True) < 2:
            axis.set_title(f"ALE: {feature} (insufficient variation)")
            axis.axis("off")
            continue
        effects = ale(X=train_validation[FEATURES], model=ale_model, feature=[feature], plot=False)
        axis.plot(effects.index, effects["eff"], marker="o", markersize=3)
        axis.axhline(0, color="gray", linestyle="--", linewidth=1)
        axis.set_title(f"ALE: {feature}")
        axis.set_xlabel(feature)
        axis.set_ylabel("Effect on predicted presence")
    ale_plot.tight_layout()
    ale_path = output_dir / f"ale_{safe_name}.png"
    ale_plot.savefig(ale_path, dpi=160)
    plt.close(ale_plot)
    return {
        "disease_class": disease,
        "artifact": artifact_path.name,
        "ale_plot": ale_path.name,
        "features": FEATURES,
        "best_validation_auroc": round(best_auc, 4),
        "metrics": metrics,
        "shap_mean_absolute_values": global_importance,
        "training_rows": int(len(train_validation)),
        "test_rows": int(len(test)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("datasets/environmental/verified-environmental-observations.csv"),
        help="Admin-exported CSV containing only verified and research-consented labels.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/environmental"))
    args = parser.parse_args()
    if not args.data.is_file():
        raise SystemExit(
            f"Training data not found: {args.data}. Collect and expert-verify consented field observations first."
        )

    frame = load_training_data(args.data)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    failures = {}
    for disease in sorted(frame["disease_class"].unique()):
        try:
            results[disease] = train_disease_model(frame, disease, args.output_dir)
        except ValueError as exc:
            failures[disease] = str(exc)
    report = {
        "model_type": "XGBoost binary classifier per disease",
        "target": "expert-verified disease presence versus absence at field observation time",
        "forecast_claim": "not a future disease forecast; temporal test metrics do not establish lead-time prediction",
        "features": FEATURES,
        "label_requirements": "verified disease labels with explicit research consent",
        "trained_models": results,
        "not_trained": failures,
    }
    report_path = args.output_dir / "verified_risk_metrics.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not results:
        raise SystemExit("No disease model met the minimum verified-label and temporal-validation requirements.")


if __name__ == "__main__":
    main()
