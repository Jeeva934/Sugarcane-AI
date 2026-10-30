from app.models import Farm, User
from app.services.security import hash_password

def test_risk_prediction_and_shap_explanation(client, monkeypatch):
    import app.api.routes as routes

    monkeypatch.setattr(routes.settings, "enable_experimental_risk_model", True)
    monkeypatch.setattr(routes.settings, "risk_model_path", "artifacts/environmental/xgboost_risk_prototype.json")

    # Mock the risk predictor so unit test doesn't depend on network
    monkeypatch.setattr(
        routes,
        "predict_environmental_risk",
        lambda lat, lon: {
            "status": "experimental_prototype",
            "overall_risk_score": 0.825,
            "risk_category": "high",
            "disease_conduciveness_scores": {
                "red_rot": 0.85,
                "rust": 0.60,
                "wilt": 0.75
            },
            "forecast_lead_time": "7-day forecast horizon",
            "processing_time_ms": 12,
            "primary_drivers": [
                {"feature": "rh_mean_7d", "value": 84.5, "shap_importance": 1.45, "effect": "increases_risk"},
                {"feature": "temp_min_7d", "value": 25.8, "shap_importance": 0.92, "effect": "increases_risk"}
            ],
            "weather_summary": {
                "temperature_mean_7d": 29.5,
                "temperature_min_7d": 25.8,
                "relative_humidity_7d": 84.5,
                "precipitation_sum_7d": 62.0,
                "thi_index": 78.2
            },
            "scientific_disclosure": "Experimental prototype based on agrometeorological parameters (ICAR-SBI/RPCAU)."
        }
    )

    client.post("/api/v1/auth/register", json={
        "email": "farmer@example.com",
        "password": "Password12345!",
        "full_name": "Farmer Selvan",
        "preferred_language": "ta"
    })

    farm = client.post("/api/v1/farms", json={
        "name": "Coimbatore Cane Plot",
        "latitude": 11.00,
        "longitude": 76.96,
        "crop_variety": "Co 86032"
    }).json()

    res = client.post("/api/v1/risk/predict", json={
        "farm_id": farm["id"],
        "disease_class": "CompositeRisk"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "experimental_prototype"
    assert data["overall_risk_score"] == 0.825
    assert data["risk_category"] == "high"
    assert data["forecast_lead_time"] == "7-day forecast horizon"
    assert len(data["primary_drivers"]) == 2
    assert data["saved_to_history"] is True

    pred_id = data["id"]
    expl_res = client.get(f"/api/v1/risk/{pred_id}/explanation")
    assert expl_res.status_code == 200
    expl_data = expl_res.json()
    assert expl_data["status"] == "available"
    assert expl_data["explanation_type"] == "shap_tree"
    assert len(expl_data["drivers"]) == 2

