import logging
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from threading import Lock
from time import perf_counter
import joblib
import numpy as np
import pandas as pd
import httpx
import shap

from app.core.config import settings

logger = logging.getLogger(__name__)
_risk_lock = Lock()
_model_cache = {}

FEATURE_COLS = [
    "temp_mean_7d", "temp_min_7d", "temp_max_7d", "rh_mean_7d", "dew_point_7d", "precip_sum_7d", "precip_days_7d",
    "temp_mean_14d", "temp_min_14d", "temp_max_14d", "rh_mean_14d", "dew_point_14d", "precip_sum_14d", "precip_days_14d",
    "thi_index", "temp_mean_lag7", "rh_mean_lag7", "precip_sum_lag7"
]

class RiskModelUnavailable(Exception):
    pass

def load_risk_pipeline():
    with _risk_lock:
        if "model" in _model_cache:
            return _model_cache["model"], _model_cache["explainer"]
            
        model_path = Path("artifacts/environmental/xgboost_risk_prototype.joblib")
        if not model_path.is_file():
            # Fallback to json if joblib not present
            json_path = Path("artifacts/environmental/xgboost_risk_prototype.json")
            if not json_path.is_file():
                raise RiskModelUnavailable("Configured risk model artifact was not found.")
            import xgboost as xgb
            model = xgb.XGBClassifier()
            model.load_model(str(json_path))
        else:
            model = joblib.load(model_path)
            
        explainer = shap.TreeExplainer(model)
        _model_cache["model"] = model
        _model_cache["explainer"] = explainer
        return model, explainer

def fetch_weather_history_features(lat: float, lon: float) -> dict:
    """Fetch 14-day recent daily weather from Open-Meteo to compute exact rolling features."""
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=25) # 25 days to cover 14-day rolling + 7-day lag
    
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "daily": [
            "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
            "relative_humidity_2m_mean", "dew_point_2m_mean", "precipitation_sum", "wind_speed_10m_max"
        ],
        "timezone": "UTC"
    }
    
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            daily = resp.json().get("daily", {})
            df = pd.DataFrame(daily)
    except Exception as exc:
        logger.warning("Could not fetch historical archive for risk features: %s. Using forecast fallback.", exc)
        # Fallback to standard forecast endpoint
        fc_url = "https://api.open-meteo.com/v1/forecast"
        fc_params = {
            "latitude": lat,
            "longitude": lon,
            "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"],
            "current": "temperature_2m,relative_humidity_2m,dew_point_2m,precipitation",
            "timezone": "UTC"
        }
        try:
            with httpx.Client(timeout=6.0) as client:
                resp = client.get(fc_url, params=fc_params)
                resp.raise_for_status()
                curr = resp.json().get("current", {})
                t_curr = curr.get("temperature_2m", 28.0)
                rh_curr = curr.get("relative_humidity_2m", 75.0)
                dew_curr = curr.get("dew_point_2m", 22.0)
                p_curr = curr.get("precipitation", 5.0)
        except Exception:
            # Climatological regional baseline fallback
            t_curr = 28.0
            rh_curr = 72.0
            dew_curr = 21.5
            p_curr = 3.0
            
        # Construct synthetic rolling approximation from current / baseline
        return {
            "temp_mean_7d": t_curr, "temp_min_7d": t_curr - 4.0, "temp_max_7d": t_curr + 4.0,
            "rh_mean_7d": rh_curr, "dew_point_7d": dew_curr, "precip_sum_7d": p_curr * 7.0, "precip_days_7d": 3.0,
            "temp_mean_14d": t_curr, "temp_min_14d": t_curr - 4.0, "temp_max_14d": t_curr + 4.0,
            "rh_mean_14d": rh_curr, "dew_point_14d": dew_curr, "precip_sum_14d": p_curr * 14.0, "precip_days_14d": 6.0,
            "thi_index": (1.8 * t_curr + 32) - ((0.55 - 0.0055 * rh_curr) * (1.8 * t_curr - 26)),
            "temp_mean_lag7": t_curr, "rh_mean_lag7": rh_curr, "precip_sum_lag7": p_curr * 7.0
        }
            
    df = df.sort_values("time").reset_index(drop=True)
    for window in [7, 14]:
        df[f"temp_mean_{window}d"] = df["temperature_2m_mean"].rolling(window, min_periods=1).mean()
        df[f"temp_min_{window}d"] = df["temperature_2m_min"].rolling(window, min_periods=1).mean()
        df[f"temp_max_{window}d"] = df["temperature_2m_max"].rolling(window, min_periods=1).mean()
        df[f"rh_mean_{window}d"] = df["relative_humidity_2m_mean"].rolling(window, min_periods=1).mean()
        df[f"dew_point_{window}d"] = df["dew_point_2m_mean"].rolling(window, min_periods=1).mean()
        df[f"precip_sum_{window}d"] = df["precipitation_sum"].rolling(window, min_periods=1).sum()
        df[f"precip_days_{window}d"] = (df["precipitation_sum"] > 1.0).rolling(window, min_periods=1).sum()
        
    t = df["temperature_2m_mean"]
    rh = df["relative_humidity_2m_mean"]
    df["thi_index"] = (1.8 * t + 32) - ((0.55 - 0.0055 * rh) * (1.8 * t - 26))
    df["temp_mean_lag7"] = df["temp_mean_7d"].shift(7).bfill()
    df["rh_mean_lag7"] = df["rh_mean_7d"].shift(7).bfill()
    df["precip_sum_lag7"] = df["precip_sum_7d"].shift(7).bfill()
    
    last_row = df.iloc[-1]
    return {col: float(last_row[col]) for col in FEATURE_COLS}

def predict_environmental_risk(lat: float, lon: float, custom_features: dict | None = None) -> dict:
    started = perf_counter()
    model, explainer = load_risk_pipeline()
    
    if custom_features and all(k in custom_features for k in FEATURE_COLS):
        feat_dict = custom_features
    else:
        feat_dict = fetch_weather_history_features(lat, lon)
        
    feat_df = pd.DataFrame([feat_dict])[FEATURE_COLS]
    prob_high = float(model.predict_proba(feat_df)[0, 1])
    
    # Tier classification
    category = "high" if prob_high >= 0.65 else ("moderate" if prob_high >= 0.35 else "low")
    
    # Specific disease conduciveness approximations
    t_min = feat_dict["temp_min_7d"]
    rh = feat_dict["rh_mean_7d"]
    precip = feat_dict["precip_sum_7d"]
    
    # Sub-disease indices
    red_rot_idx = min(1.0, max(0.0, 0.4 * (1.0 if 28 <= feat_dict["temp_mean_7d"] <= 33 else 0.5) + 0.4 * ((rh - 60) / 30) + 0.2 * (precip / 45)))
    rust_idx = min(1.0, max(0.0, 0.5 * (1.0 if 20 <= feat_dict["temp_mean_7d"] <= 26 else 0.5) + 0.4 * ((rh - 65) / 25) + 0.1 * (precip / 30)))
    wilt_idx = min(1.0, max(0.0, 0.5 * ((t_min - 20) / 6) + 0.5 * ((rh - 60) / 30)))
    
    # Local SHAP Explanation
    shap_vals = explainer(feat_df)
    vals = shap_vals.values[0]
    
    top_drivers = []
    for col, v in zip(FEATURE_COLS, vals):
        top_drivers.append({
            "feature": col,
            "value": round(feat_dict[col], 2),
            "shap_importance": round(float(v), 3),
            "effect": "increases_risk" if v > 0 else "decreases_risk"
        })
    top_drivers.sort(key=lambda d: abs(d["shap_importance"]), reverse=True)
    
    return {
        "status": "experimental_prototype",
        "overall_risk_score": round(prob_high, 4),
        "risk_category": category,
        "disease_conduciveness_scores": {
            "red_rot": round(red_rot_idx, 3),
            "rust": round(rust_idx, 3),
            "wilt": round(wilt_idx, 3)
        },
        "forecast_lead_time": "7-day forecast horizon",
        "processing_time_ms": round((perf_counter() - started) * 1000),
        "primary_drivers": top_drivers[:5],
        "weather_summary": {
            "temperature_mean_7d": round(feat_dict["temp_mean_7d"], 1),
            "temperature_min_7d": round(feat_dict["temp_min_7d"], 1),
            "relative_humidity_7d": round(feat_dict["rh_mean_7d"], 1),
            "precipitation_sum_7d": round(feat_dict["precip_sum_7d"], 1),
            "thi_index": round(feat_dict["thi_index"], 1)
        },
        "scientific_disclosure": (
            "This assessment represents theoretical microclimatic conduciveness (ICAR-SBI/RPCAU parameters) "
            "and serves as an experimental early-warning prototype. It is NOT a confirmed biological disease occurrence."
        )
    }

