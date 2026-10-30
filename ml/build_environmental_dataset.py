import json
import math
import httpx
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Target Agricultural Research Stations
STATIONS = {
    "Pusa_Bihar": {
        "institution": "Dr. Rajendra Prasad Central Agricultural University (RPCAU), SRI Pusa",
        "latitude": 25.98,
        "longitude": 85.67,
        "climate": "Subtropical",
        "primary_diseases": ["RedRot", "Wilt", "Rust"]
    },
    "Coimbatore_TN": {
        "institution": "ICAR - Sugarcane Breeding Institute (SBI), Coimbatore",
        "latitude": 11.00,
        "longitude": 76.96,
        "climate": "Tropical",
        "primary_diseases": ["RedRot", "Rust", "YellowLeaf", "Mosaic"]
    },
    "Pune_MH": {
        "institution": "Vasantdada Sugar Institute (VSI), Pune / Maharashtra Belt",
        "latitude": 18.52,
        "longitude": 73.85,
        "climate": "Tropical Semi-Arid",
        "primary_diseases": ["Rust", "YellowLeaf", "Mosaic"]
    }
}

def fetch_historical_weather(lat: float, lon: float, start_date: str, end_date: str) -> pd.DataFrame:
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "temperature_2m_mean",
            "relative_humidity_2m_mean",
            "dew_point_2m_mean",
            "precipitation_sum",
            "wind_speed_10m_max"
        ],
        "timezone": "UTC"
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()["daily"]
        
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    return df

def compute_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("time").reset_index(drop=True).copy()
    
    # 7-day and 14-day rolling windows
    for window in [7, 14]:
        df[f"temp_mean_{window}d"] = df["temperature_2m_mean"].rolling(window, min_periods=window).mean()
        df[f"temp_min_{window}d"] = df["temperature_2m_min"].rolling(window, min_periods=window).mean()
        df[f"temp_max_{window}d"] = df["temperature_2m_max"].rolling(window, min_periods=window).mean()
        df[f"rh_mean_{window}d"] = df["relative_humidity_2m_mean"].rolling(window, min_periods=window).mean()
        df[f"dew_point_{window}d"] = df["dew_point_2m_mean"].rolling(window, min_periods=window).mean()
        df[f"precip_sum_{window}d"] = df["precipitation_sum"].rolling(window, min_periods=window).sum()
        df[f"precip_days_{window}d"] = (df["precipitation_sum"] > 1.0).rolling(window, min_periods=window).sum()
        
    # Temperature-Humidity Conduciveness Index (THI)
    t = df["temperature_2m_mean"]
    rh = df["relative_humidity_2m_mean"]
    df["thi_index"] = (1.8 * t + 32) - ((0.55 - 0.0055 * rh) * (1.8 * t - 26))
    
    # Lagged features (7 days prior - forecasting lead time)
    df["temp_mean_lag7"] = df["temp_mean_7d"].shift(7)
    df["rh_mean_lag7"] = df["rh_mean_7d"].shift(7)
    df["precip_sum_lag7"] = df["precip_sum_7d"].shift(7)
    
    return df

def assign_theoretical_conduciveness_index(row: pd.Series) -> dict:
    """
    CRITICAL METHODOLOGICAL NOTICE:
    These indices represent THEORETICAL MICROCLIMATIC CONDUCIVENESS derived from 
    peer-reviewed sugarcane pathology literature (ICAR-SBI; Kumar & Minnatullah 2025).
    They DO NOT represent empirical field disease observations and must NOT be used 
    to claim validated empirical disease incidence prediction.
    """
    temp_7d = row.get("temp_mean_7d")
    temp_min_7d = row.get("temp_min_7d")
    rh_7d = row.get("rh_mean_7d")
    precip_7d = row.get("precip_sum_7d", 0.0)
    
    if pd.isna(temp_7d) or pd.isna(rh_7d) or pd.isna(temp_min_7d):
        return {
            "heuristic_red_rot_index": 0.15,
            "heuristic_rust_index": 0.15,
            "heuristic_wilt_index": 0.15,
            "heuristic_conduciveness_score": 0.15,
            "heuristic_risk_category": "low"
        }
        
    # Red Rot Conduciveness Index - Peak when Temp 28-32°C, RH > 80%, high rainfall
    rr_temp_score = 1.0 if 28.0 <= temp_7d <= 33.0 else max(0.0, 1.0 - abs(temp_7d - 30.5) * 0.18)
    rr_rh_score = min(1.0, max(0.0, (rh_7d - 60.0) / 30.0))
    rr_precip_score = min(1.0, precip_7d / 45.0)
    rr_score = 0.40 * rr_temp_score + 0.40 * rr_rh_score + 0.20 * rr_precip_score
    
    # Rust Conduciveness Index - Peak when Temp 20-26°C, RH > 75%
    rust_temp_score = 1.0 if 20.0 <= temp_7d <= 26.0 else max(0.0, 1.0 - abs(temp_7d - 23.0) * 0.20)
    rust_rh_score = min(1.0, max(0.0, (rh_7d - 65.0) / 25.0))
    rust_score = 0.50 * rust_temp_score + 0.40 * rust_rh_score + 0.10 * min(1.0, precip_7d / 30.0)
    
    # Wilt Conduciveness Index (Kumar & Minnatullah 2025: High min temp > 24°C + high humidity)
    wilt_temp_score = min(1.0, max(0.0, (temp_min_7d - 20.0) / 6.0))
    wilt_rh_score = min(1.0, max(0.0, (rh_7d - 60.0) / 30.0))
    wilt_score = 0.50 * wilt_temp_score + 0.50 * wilt_rh_score
    
    overall_score = max(rr_score, rust_score, wilt_score)
    category = "high" if overall_score >= 0.70 else ("moderate" if overall_score >= 0.40 else "low")
    
    return {
        "heuristic_red_rot_index": round(float(rr_score), 4),
        "heuristic_rust_index": round(float(rust_score), 4),
        "heuristic_wilt_index": round(float(wilt_score), 4),
        "heuristic_conduciveness_score": round(float(overall_score), 4),
        "heuristic_risk_category": category
    }

def build_dataset():
    print("Building historical meteorological feature dataset (2021-2024)...")
    start_date = "2021-01-01"
    end_date = "2024-12-31"
    
    all_frames = []
    
    for station_name, info in STATIONS.items():
        print(f"Fetching historical weather for {station_name} ({info['institution']})...")
        df_raw = fetch_historical_weather(info["latitude"], info["longitude"], start_date, end_date)
        df_raw["station"] = station_name
        df_raw["climate_zone"] = info["climate"]
        df_raw["latitude"] = info["latitude"]
        df_raw["longitude"] = info["longitude"]
        
        df_features = compute_rolling_features(df_raw)
        
        # Apply theoretical conduciveness index
        conduciveness = df_features.apply(assign_theoretical_conduciveness_index, axis=1)
        conduciveness_df = pd.DataFrame(list(conduciveness))
        
        combined = pd.concat([df_features, conduciveness_df], axis=1)
        # Drop warm-up rows with NaNs from rolling/lagged windows (first 21 days)
        combined = combined.dropna().reset_index(drop=True)
        all_frames.append(combined)
        
    full_dataset = pd.concat(all_frames, axis=0).reset_index(drop=True)
    
    # Save CSV
    out_dir = Path("datasets/environmental")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "sugarcane_environmental_risk_dataset.csv"
    full_dataset.to_csv(csv_path, index=False)
    
    print(f"\nGenerated {len(full_dataset)} daily observation records across 3 agricultural research stations.")
    print(f"Saved to: {csv_path}")
    
    # Check empirical dataset presence
    empirical_csv = out_dir / "kumar_minnatullah_empirical_observations.csv"
    empirical_records = 0
    if empirical_csv.exists():
        emp_df = pd.read_csv(empirical_csv)
        empirical_records = len(emp_df)
        print(f"Found {empirical_records} digitized empirical field observations from published literature.")
    
    # Create Temporal Split (Train: 2021-2023, Test: 2024)
    train_temporal = full_dataset[full_dataset["time"].dt.year < 2024]
    test_temporal = full_dataset[full_dataset["time"].dt.year == 2024]
    
    # Create Spatial Split (Train: Pusa & Pune, Test: Coimbatore)
    train_spatial = full_dataset[full_dataset["station"] != "Coimbatore_TN"]
    test_spatial = full_dataset[full_dataset["station"] == "Coimbatore_TN"]
    
    split_info = {
        "dataset_architecture": "dual_track",
        "critical_methodological_notice": (
            "In accordance with rigorous academic integrity protocols, theoretical heuristic conduciveness "
            "scores derived from weather thresholds are NOT claimed as validated empirical disease incidence labels. "
            "True empirical validation requires matched ground-truth disease incidence observations from field trials."
        ),
        "empirical_ground_truth_dataset": {
            "file": "datasets/environmental/kumar_minnatullah_empirical_observations.csv",
            "citation": "Kumar & Minnatullah et al. (2025), Int. J. Environ. Clim. Change, RPCAU Pusa",
            "records": empirical_records,
            "monitored_disease": "Sugarcane Wilt (Fusarium sacchari)",
            "monitored_period": "2023-06 to 2024-01 (16 fortnights)",
            "reported_r2": 0.878
        },
        "meteorological_feature_dataset": {
            "file": "datasets/environmental/sugarcane_environmental_risk_dataset.csv",
            "total_records": len(full_dataset),
            "stations": list(STATIONS.keys()),
            "date_range": [start_date, end_date],
            "feature_columns": [
                "temp_mean_7d", "temp_min_7d", "temp_max_7d", "rh_mean_7d", "dew_point_7d", "precip_sum_7d", "precip_days_7d",
                "temp_mean_14d", "temp_min_14d", "temp_max_14d", "rh_mean_14d", "dew_point_14d", "precip_sum_14d", "precip_days_14d",
                "thi_index", "temp_mean_lag7", "rh_mean_lag7", "precip_sum_lag7"
            ],
            "heuristic_conduciveness_columns": [
                "heuristic_conduciveness_score", "heuristic_risk_category", 
                "heuristic_red_rot_index", "heuristic_rust_index", "heuristic_wilt_index"
            ],
            "temporal_split": {
                "train_years": "2021-2023",
                "train_records": len(train_temporal),
                "test_year": "2024",
                "test_records": len(test_temporal)
            },
            "spatial_split": {
                "train_stations": ["Pusa_Bihar", "Pune_MH"],
                "train_records": len(train_spatial),
                "test_station": "Coimbatore_TN",
                "test_records": len(test_spatial)
            },
            "heuristic_distribution": full_dataset["heuristic_risk_category"].value_counts().to_dict()
        }
    }
    
    with open(out_dir / "dataset_summary.json", "w") as f:
        json.dump(split_info, f, indent=2)
    print("Dataset summary updated with strict methodological disclosures.")

if __name__ == "__main__":
    build_dataset()