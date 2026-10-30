import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from sklearn.linear_model import LinearRegression, Ridge, LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    r2_score, mean_absolute_error, mean_squared_error,
    accuracy_score, f1_score, precision_score, recall_score,
    roc_auc_score, average_precision_score, brier_score_loss,
    roc_curve, precision_recall_curve
)
from sklearn.calibration import calibration_curve
from sklearn.model_selection import ParameterGrid

import xgboost as xgb
import shap
from PyALE import ale

FEATURE_COLS = [
    "temp_mean_7d", "temp_min_7d", "temp_max_7d", "rh_mean_7d", "dew_point_7d", "precip_sum_7d", "precip_days_7d",
    "temp_mean_14d", "temp_min_14d", "temp_max_14d", "rh_mean_14d", "dew_point_14d", "precip_sum_14d", "precip_days_14d",
    "thi_index", "temp_mean_lag7", "rh_mean_lag7", "precip_sum_lag7"
]

class ModelProbWrapper:
    """Wrapper for PyALE to predict single continuous probability."""
    def __init__(self, model):
        self.model = model
    def predict(self, X):
        return self.model.predict_proba(X)[:, 1]

def evaluate_empirical_baseline():
    """Track 1: Multiple Linear Regression on Kumar & Minnatullah (2025) real field data."""
    print("\n=======================================================")
    print("TRACK 1: EMPIRICAL GROUND-TRUTH BASELINE (RPCAU Pusa Field Data)")
    print("=======================================================")
    emp_path = Path("datasets/environmental/kumar_minnatullah_empirical_observations.csv")
    if not emp_path.exists():
        print("Empirical dataset missing.")
        return None
        
    df_emp = pd.read_csv(emp_path)
    feat_cols = ["min_temp_c", "max_temp_c", "morning_rh_pct", "evening_rh_pct", "rainfall_mm", "sunshine_hours"]
    X = df_emp[feat_cols]
    y = df_emp["wilt_incidence_pct"]
    
    # Fit Multiple Linear Regression
    lr = Ridge(alpha=1.0)
    lr.fit(X, y)
    y_pred = lr.predict(X)
    
    r2 = r2_score(y, y_pred)
    mae = mean_absolute_error(y, y_pred)
    rmse = np.sqrt(mean_squared_error(y, y_pred))
    
    # Leave-One-Out Cross Validation
    loo_preds = []
    for i in range(len(df_emp)):
        train_idx = [j for j in range(len(df_emp)) if j != i]
        m = Ridge(alpha=1.0)
        m.fit(X.iloc[train_idx], y.iloc[train_idx])
        loo_preds.append(m.predict(X.iloc[[i]])[0])
    loo_r2 = r2_score(y, loo_preds)
    loo_mae = mean_absolute_error(y, loo_preds)
    
    print(f"Empirical Records: {len(df_emp)} fortnights")
    print(f"Full-Sample R²: {r2:.4f} (Paper reported: 0.878)")
    print(f"Full-Sample MAE: {mae:.2f}% incidence")
    print(f"LOOCV Cross-Validated R²: {loo_r2:.4f}")
    print(f"LOOCV Cross-Validated MAE: {loo_mae:.2f}% incidence")
    
    coef_dict = dict(zip(feat_cols, [round(c, 4) for c in lr.coef_]))
    print("Regression Coefficients (Epidemiological drivers):", coef_dict)
    
    return {
        "sample_size": len(df_emp),
        "full_sample_r2": round(float(r2), 4),
        "full_sample_mae": round(float(mae), 4),
        "full_sample_rmse": round(float(rmse), 4),
        "loocv_r2": round(float(loo_r2), 4),
        "loocv_mae": round(float(loo_mae), 4),
        "coefficients": coef_dict
    }

def train_and_evaluate_xgboost():
    """Track 2: Meteorological Feature Dataset (4,344 daily records across 3 stations)."""
    print("\n=======================================================")
    print("TRACK 2: ENVIRONMENTAL RISK MODEL (XGBoost Prototype)")
    print("=======================================================")
    
    out_dir = Path("artifacts/environmental")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    data_path = Path("datasets/environmental/sugarcane_environmental_risk_dataset.csv")
    df = pd.read_csv(data_path)
    df["time"] = pd.to_datetime(df["time"])
    
    # Target: High-Risk vs Low/Moderate (Binary Elevated Risk Warning)
    df["target_high_risk"] = (df["heuristic_risk_category"] == "high").astype(int)
    
    # 1. Temporal Partitions
    train_val_df = df[df["time"].dt.year < 2024].copy()
    test_df = df[df["time"].dt.year == 2024].copy()
    
    # Sub-split train_val for tuning (2021-2022 train, 2023 val)
    train_tune_df = train_val_df[train_val_df["time"].dt.year <= 2022].copy()
    val_tune_df = train_val_df[train_val_df["time"].dt.year == 2023].copy()
    
    X_train_tune = train_tune_df[FEATURE_COLS]
    y_train_tune = train_tune_df["target_high_risk"]
    X_val_tune = val_tune_df[FEATURE_COLS]
    y_val_tune = val_tune_df["target_high_risk"]
    
    X_train_full = train_val_df[FEATURE_COLS]
    y_train_full = train_val_df["target_high_risk"]
    X_test = test_df[FEATURE_COLS]
    y_test = test_df["target_high_risk"]
    
    print(f"Temporal Split - Train (2021-2023): {len(train_val_df)} | Test (2024): {len(test_df)}")
    print(f"Test Class Balance - High Risk: {y_test.sum()} ({y_test.mean()*100:.1f}%) | Normal: {len(y_test)-y_test.sum()}")
    
    # 2. Linear Baseline Model (Logistic Regression)
    print("\nTraining Linear Baseline (Logistic Regression)...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_full)
    X_test_scaled = scaler.transform(X_test)
    
    lr = LogisticRegression(max_iter=1000, random_state=42)
    lr.fit(X_train_scaled, y_train_full)
    lr_pred_prob = lr.predict_proba(X_test_scaled)[:, 1]
    lr_pred = lr.predict(X_test_scaled)
    
    baseline_metrics = {
        "accuracy": round(float(accuracy_score(y_test, lr_pred)), 4),
        "macro_f1": round(float(f1_score(y_test, lr_pred, average="macro")), 4),
        "auroc": round(float(roc_auc_score(y_test, lr_pred_prob)), 4),
        "auprc": round(float(average_precision_score(y_test, lr_pred_prob)), 4),
        "brier_score": round(float(brier_score_loss(y_test, lr_pred_prob)), 4)
    }
    print("Baseline Metrics (Logistic Regression):", baseline_metrics)
    
    # 3. Hyperparameter Tuning for XGBoost
    print("\nTuning XGBoost hyperparameters on 2023 validation set...")
    param_grid = {
        "max_depth": [3, 4, 5],
        "learning_rate": [0.03, 0.05, 0.1],
        "n_estimators": [60, 100, 150],
        "subsample": [0.8, 1.0],
        "colsample_bytree": [0.8, 1.0]
    }
    
    best_val_auc = -1.0
    best_params = None
    
    for p in ParameterGrid(param_grid):
        model = xgb.XGBClassifier(
            **p,
            eval_metric="logloss",
            random_state=42
        )
        model.fit(X_train_tune, y_train_tune)
        val_probs = model.predict_proba(X_val_tune)[:, 1]
        val_auc = roc_auc_score(y_val_tune, val_probs)
        if val_auc > best_val_auc:
            best_val_auc = val_auc
            best_params = p
            
    print(f"Optimal Hyperparameters: {best_params} (Validation AUROC: {best_val_auc:.4f})")
    
    # 4. Train Final Tuned XGBoost on Full 2021-2023 Training Set
    best_xgb = xgb.XGBClassifier(
        **best_params,
        eval_metric="logloss",
        random_state=42
    )
    best_xgb.fit(X_train_full, y_train_full)
    
    # 5. Evaluate on 2024 Unseen Test Set
    y_test_prob = best_xgb.predict_proba(X_test)[:, 1]
    y_test_pred = (y_test_prob >= 0.50).astype(int)
    
    xgb_metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_test_pred)), 4),
        "macro_f1": round(float(f1_score(y_test, y_test_pred, average="macro")), 4),
        "precision": round(float(precision_score(y_test, y_test_pred)), 4),
        "recall": round(float(recall_score(y_test, y_test_pred)), 4),
        "auroc": round(float(roc_auc_score(y_test, y_test_prob)), 4),
        "auprc": round(float(average_precision_score(y_test, y_test_prob)), 4),
        "brier_score": round(float(brier_score_loss(y_test, y_test_prob)), 4)
    }
    print("\nTuned XGBoost Test Metrics (2024 Out-of-Time):", xgb_metrics)
    
    # 6. Spatial Generalization Test (Train on Pusa & Pune, Test on Coimbatore)
    train_spatial = df[df["station"] != "Coimbatore_TN"]
    test_spatial = df[df["station"] == "Coimbatore_TN"]
    
    spat_xgb = xgb.XGBClassifier(**best_params, eval_metric="logloss", random_state=42)
    spat_xgb.fit(train_spatial[FEATURE_COLS], train_spatial["target_high_risk"])
    spat_prob = spat_xgb.predict_proba(test_spatial[FEATURE_COLS])[:, 1]
    spat_pred = (spat_prob >= 0.50).astype(int)
    
    spatial_metrics = {
        "test_station": "Coimbatore_TN",
        "sample_size": len(test_spatial),
        "accuracy": round(float(accuracy_score(test_spatial["target_high_risk"], spat_pred)), 4),
        "macro_f1": round(float(f1_score(test_spatial["target_high_risk"], spat_pred, average="macro")), 4),
        "auroc": round(float(roc_auc_score(test_spatial["target_high_risk"], spat_prob)), 4),
        "auprc": round(float(average_precision_score(test_spatial["target_high_risk"], spat_prob)), 4)
    }
    print("Spatial Generalization (Coimbatore):", spatial_metrics)
    
    # 7. Probability Calibration & Evaluation Plots
    print("\nGenerating Evaluation & Calibration Plots...")
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    # ROC Curve
    fpr, tpr, _ = roc_curve(y_test, y_test_prob)
    fpr_bl, tpr_bl, _ = roc_curve(y_test, lr_pred_prob)
    axes[0].plot(fpr, tpr, color='#1E88E5', lw=2.5, label=f'XGBoost (AUC = {xgb_metrics["auroc"]:.3f})')
    axes[0].plot(fpr_bl, tpr_bl, color='#FB8C00', lw=2, linestyle='--', label=f'Logistic Reg (AUC = {baseline_metrics["auroc"]:.3f})')
    axes[0].plot([0, 1], [0, 1], color='gray', linestyle=':')
    axes[0].set_title('ROC Curve (2024 Test Set)', fontsize=12, fontweight='bold')
    axes[0].set_xlabel('False Positive Rate')
    axes[0].set_ylabel('True Positive Rate')
    axes[0].legend(loc='lower right')
    axes[0].grid(True, alpha=0.3)
    
    # Precision-Recall Curve
    pr_prec, pr_rec, _ = precision_recall_curve(y_test, y_test_prob)
    pr_prec_bl, pr_rec_bl, _ = precision_recall_curve(y_test, lr_pred_prob)
    axes[1].plot(pr_rec, pr_prec, color='#1E88E5', lw=2.5, label=f'XGBoost (AUPRC = {xgb_metrics["auprc"]:.3f})')
    axes[1].plot(pr_rec_bl, pr_prec_bl, color='#FB8C00', lw=2, linestyle='--', label=f'Logistic Reg (AUPRC = {baseline_metrics["auprc"]:.3f})')
    axes[1].set_title('Precision-Recall Curve', fontsize=12, fontweight='bold')
    axes[1].set_xlabel('Recall')
    axes[1].set_ylabel('Precision')
    axes[1].legend(loc='lower left')
    axes[1].grid(True, alpha=0.3)
    
    # Calibration Curve
    fraction_of_positives, mean_predicted_value = calibration_curve(y_test, y_test_prob, n_bins=10)
    frac_bl, mean_bl = calibration_curve(y_test, lr_pred_prob, n_bins=10)
    axes[2].plot(mean_predicted_value, fraction_of_positives, 's-', color='#1E88E5', lw=2, label=f'XGBoost (Brier={xgb_metrics["brier_score"]:.3f})')
    axes[2].plot(mean_bl, frac_bl, 'o--', color='#FB8C00', lw=2, label=f'Logistic Reg (Brier={baseline_metrics["brier_score"]:.3f})')
    axes[2].plot([0, 1], [0, 1], color='gray', linestyle=':', label='Perfect Calibration')
    axes[2].set_title('Reliability Calibration Curve', fontsize=12, fontweight='bold')
    axes[2].set_xlabel('Mean Predicted Probability')
    axes[2].set_ylabel('Fraction of Positives')
    axes[2].legend(loc='upper left')
    axes[2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(out_dir / "model_evaluation_curves.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved: artifacts/environmental/model_evaluation_curves.png")
    
    # 8. SHAP Explanations
    print("\nComputing SHAP values for XGBoost model...")
    explainer = shap.TreeExplainer(best_xgb)
    shap_values = explainer(X_test)
    
    # SHAP Summary Beeswarm
    fig = plt.figure(figsize=(10, 7))
    shap.summary_plot(shap_values, X_test, show=False, max_display=12)
    plt.title("SHAP Beeswarm: Environmental Feature Contributions", fontsize=13, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig(out_dir / "shap_summary_beeswarm.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("Saved: artifacts/environmental/shap_summary_beeswarm.png")
    
    # SHAP Feature Importance Bar
    fig = plt.figure(figsize=(10, 6))
    shap.plots.bar(shap_values, max_display=12, show=False)
    plt.title("SHAP Feature Importance (Mean |SHAP Value|)", fontsize=13, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig(out_dir / "shap_feature_importance.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("Saved: artifacts/environmental/shap_feature_importance.png")
    
    # Local SHAP Waterfall Plots
    # High-Risk Sample (highest prediction prob in test set)
    high_idx = int(np.argmax(y_test_prob))
    fig = plt.figure(figsize=(9, 5))
    shap.plots.waterfall(shap_values[high_idx], max_display=10, show=False)
    plt.title(f"Local SHAP Explanation: High-Risk Alert Day (Date: {test_df.iloc[high_idx]['time'].strftime('%Y-%m-%d')}, P={y_test_prob[high_idx]:.2f})", fontsize=11, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig(out_dir / "shap_waterfall_high_risk.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("Saved: artifacts/environmental/shap_waterfall_high_risk.png")
    
    # Low-Risk Sample (lowest prediction prob in test set)
    low_idx = int(np.argmin(y_test_prob))
    fig = plt.figure(figsize=(9, 5))
    shap.plots.waterfall(shap_values[low_idx], max_display=10, show=False)
    plt.title(f"Local SHAP Explanation: Low-Risk Safe Day (Date: {test_df.iloc[low_idx]['time'].strftime('%Y-%m-%d')}, P={y_test_prob[low_idx]:.2f})", fontsize=11, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig(out_dir / "shap_waterfall_low_risk.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("Saved: artifacts/environmental/shap_waterfall_low_risk.png")
    
    # 9. ALE (Accumulated Local Effects) Plots
    print("\nComputing ALE Plots for Core Environmental Parameters...")
    ale_wrapper = ModelProbWrapper(best_xgb)
    selected_features = ["temp_min_7d", "rh_mean_7d", "precip_sum_7d", "thi_index"]
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    
    for i, feat in enumerate(selected_features):
        ale_df = ale(
            X=X_train_full,
            model=ale_wrapper,
            feature=[feat],
            grid_size=20,
            plot=False
        )
        x_vals = ale_df.index
        y_vals = ale_df["eff"]
        
        axes[i].plot(x_vals, y_vals, color='#2E7D32', lw=2.5, marker='o', markersize=4)
        axes[i].axhline(0, color='gray', linestyle='--', alpha=0.6)
        axes[i].set_title(f'ALE: {feat}', fontsize=12, fontweight='bold')
        axes[i].set_xlabel(feat)
        axes[i].set_ylabel('Accumulated Local Effect on P(High Risk)')
        axes[i].grid(True, alpha=0.3)
        
    plt.suptitle("Accumulated Local Effects (ALE) for Key Agrometeorological Features", fontsize=14, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.savefig(out_dir / "ale_plots.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved: artifacts/environmental/ale_plots.png")
    
    # 10. Save Model Checkpoints & Metadata
    best_xgb.save_model(out_dir / "xgboost_risk_prototype.json")
    joblib.dump(best_xgb, out_dir / "xgboost_risk_prototype.joblib")
    joblib.dump(scaler, out_dir / "scaler.joblib")
    joblib.dump(lr, out_dir / "baseline_logistic_regression.joblib")
    
    print("\nModel checkpoints saved to artifacts/environmental/")
    
    return {
        "best_hyperparameters": best_params,
        "baseline_logistic_regression": baseline_metrics,
        "tuned_xgboost_2024_test": xgb_metrics,
        "spatial_generalization_coimbatore": spatial_metrics
    }

def main():
    print("Starting Phase 6: Environmental Model Training & Explainability...")
    track1_results = evaluate_empirical_baseline()
    track2_results = train_and_evaluate_xgboost()
    
    # Consolidate Metrics & Disclosures
    out_dir = Path("artifacts/environmental")
    final_report = {
        "phase": "Phase 6 — XGBoost Risk Prediction",
        "date": "2026-10-30",
        "decision_gate_compliance": {
            "status": "COMPLIANT WITH DECISION GATE",
            "disclosure": (
                "Due to the absence of continuous open multi-year daily field disease incidence scouting data, "
                "this environmental model is strictly classified and deployed as an EXPERIMENTAL PROTOTYPE "
                "(Agrometeorological Microclimatic Conduciveness System). In compliance with scientific guidelines, "
                "this module is NOT claimed as a validated biological disease incidence predictor, but rather "
                "as an early warning biometeorological risk index based on published ICAR-SBI/RPCAU parameters."
            )
        },
        "track1_empirical_literature_baseline": track1_results,
        "track2_environmental_xgboost_prototype": track2_results,
        "generated_artifacts": [
            "artifacts/environmental/xgboost_risk_prototype.json",
            "artifacts/environmental/xgboost_risk_prototype.joblib",
            "artifacts/environmental/model_evaluation_curves.png",
            "artifacts/environmental/shap_summary_beeswarm.png",
            "artifacts/environmental/shap_feature_importance.png",
            "artifacts/environmental/shap_waterfall_high_risk.png",
            "artifacts/environmental/shap_waterfall_low_risk.png",
            "artifacts/environmental/ale_plots.png"
        ]
    }
    
    with open(out_dir / "risk_metrics.json", "w") as f:
        json.dump(final_report, f, indent=2)
    print("\nSaved comprehensive evaluation report to: artifacts/environmental/risk_metrics.json")
    print("Phase 6 Training & Explainability Pipeline Complete!")

if __name__ == "__main__":
    main()

