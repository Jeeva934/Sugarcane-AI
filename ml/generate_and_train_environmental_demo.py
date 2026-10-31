"""Generate synthetic-only rows and train isolated XGBoost pipeline-demo models.

These labels are generated from arbitrary code rules; they are not disease
observations and must never be used for agronomic decisions or API inference.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

FEATURES = [
    "soil_ph",
    "temperature_c",
    "relative_humidity_pct",
    "rainfall_mm",
    "wind_speed_kmh",
    "dew_point_c",
]
DISEASES = ("Mosaic", "RedRot", "Rust", "Yellow", "Wilt")
SYNTHETIC_ONLY = (
    "SYNTHETIC DEMO ONLY. Rows and labels are programmatically invented for "
    "pipeline testing; they are not measured weather, verified disease "
    "observations, agronomic evidence, or suitable for real prediction."
)


class PositiveProbabilityModel:
    def __init__(self, model):
        self.model = model

    def predict(self, features):
        return self.model.predict_proba(features)[:, 1]


def generate_rows(rows_per_disease: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    records = []
    start = np.datetime64("2022-01-01")
    for disease in DISEASES:
        for index in range(rows_per_disease):
            temperature = float(np.clip(rng.normal(27.5, 5), 10, 43))
            humidity = float(rng.uniform(35, 100))
            rainfall = float(np.clip(rng.gamma(1.5, 5), 0, 90))
            wind = float(np.clip(rng.normal(9, 4), 0, 40))
            dew_point = float(np.clip(temperature - (100 - humidity) / 5 + rng.normal(0, 1.5), 0, temperature))
            soil_ph = float(rng.uniform(4.5, 9.0))

            # Deliberately arbitrary label rules, not disease biology.
            if disease == "RedRot":
                signal = 0.045 * (humidity - 65) + 0.035 * (rainfall - 8) + 0.08 * (temperature - 27)
            elif disease == "Rust":
                signal = 0.10 * (humidity - 70) - 0.12 * (temperature - 23) + 0.025 * rainfall
            elif disease == "Mosaic":
                signal = 0.08 * (temperature - 27) - 0.035 * (humidity - 60) + 0.04 * (wind - 8)
            elif disease == "Yellow":
                signal = 0.08 * (temperature - 28) + 0.035 * (humidity - 65) - 0.05 * (soil_ph - 6.5)
            else:
                signal = 0.09 * (temperature - 26) + 0.045 * (rainfall - 10) - 0.05 * (humidity - 65)
            probability = 1 / (1 + np.exp(-np.clip(signal / 3, -20, 20)))
            target = int(rng.random() < probability)
            records.append({
                "date": str(start + np.timedelta64(index, "D")),
                "farm_group": f"SYNTHETIC_FARM_{index % 30:02d}",
                "disease_class": disease,
                **dict(zip(FEATURES, (soil_ph, temperature, humidity, rainfall, wind, dew_point))),
                "synthetic_target": target,
                "synthetic_flag": True,
            })
    return pd.DataFrame.from_records(records)


def train_demo_models(frame: pd.DataFrame, artifact_dir: Path, seed: int) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import shap
    from PyALE import ale

    artifact_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for disease in DISEASES:
        rows = frame[frame["disease_class"] == disease]
        train, test = train_test_split(
            rows,
            test_size=0.25,
            random_state=seed,
            stratify=rows["synthetic_target"],
        )
        model = XGBClassifier(
            n_estimators=60,
            max_depth=3,
            learning_rate=0.08,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=seed,
            n_jobs=2,
        )
        model.fit(train[FEATURES], train["synthetic_target"])
        probabilities = model.predict_proba(test[FEATURES])[:, 1]
        artifact = artifact_dir / f"demo_xgboost_{disease.lower()}.json"
        model.save_model(artifact)
        shap_values = shap.TreeExplainer(model).shap_values(test[FEATURES])
        shap_importance = {
            feature: round(float(value), 6)
            for feature, value in zip(FEATURES, np.abs(shap_values).mean(axis=0))
        }

        ale_figure, axes = plt.subplots(2, 3, figsize=(14, 8))
        probability_model = PositiveProbabilityModel(model)
        for axis, feature in zip(axes.flat, FEATURES):
            effects = ale(
                X=train[FEATURES],
                model=probability_model,
                feature=[feature],
                plot=False,
            )
            axis.plot(effects.index, effects["eff"], marker="o", markersize=3)
            axis.axhline(0, color="gray", linestyle="--", linewidth=1)
            axis.set_title(f"Synthetic-demo ALE: {feature}")
            axis.set_xlabel(feature)
            axis.set_ylabel("Effect on synthetic target")
        ale_figure.tight_layout()
        ale_path = artifact_dir / f"SYNTHETIC_DEMO_ONLY_ale_{disease.lower()}.png"
        ale_figure.savefig(ale_path, dpi=120)
        plt.close(ale_figure)
        results[disease] = {
            "artifact": artifact.name,
            "ale_plot": ale_path.name,
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "demo_accuracy": round(float(accuracy_score(test["synthetic_target"], probabilities >= 0.5)), 4),
            "demo_auroc": round(float(roc_auc_score(test["synthetic_target"], probabilities)), 4),
            "synthetic_demo_mean_absolute_shap_values": shap_importance,
        }
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows-per-disease", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data-dir", type=Path, default=Path("datasets/environmental_demo"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/environmental_demo"))
    args = parser.parse_args()
    if args.rows_per_disease < 100:
        parser.error("--rows-per-disease must be at least 100 for a demo split.")

    args.data_dir.mkdir(parents=True, exist_ok=True)
    data_path = args.data_dir / "SYNTHETIC_NOT_REAL_environmental_demo.csv"
    frame = generate_rows(args.rows_per_disease, args.seed)
    frame.to_csv(data_path, index=False)
    model_results = train_demo_models(frame, args.artifact_dir, args.seed)
    report = {
        "warning": SYNTHETIC_ONLY,
        "seed": args.seed,
        "rows_per_disease": args.rows_per_disease,
        "total_rows": int(len(frame)),
        "feature_columns": FEATURES,
        "target_column": "synthetic_target",
        "generation_method": "Arbitrary hard-coded synthetic rules plus random noise; not sourced from research.",
        "dataset": str(data_path),
        "model_artifact_directory": str(args.artifact_dir),
        "models": model_results,
        "real_world_validity": False,
        "safe_for_api_prediction": False,
    }
    report_path = args.artifact_dir / "SYNTHETIC_DEMO_ONLY_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
