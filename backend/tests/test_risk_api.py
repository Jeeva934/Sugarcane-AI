def test_risk_prediction_and_shap_explanation(client, monkeypatch, tmp_path):
    import app.api.routes as routes
    from types import SimpleNamespace
    from datetime import datetime, timezone

    model_artifact = tmp_path / "xgboost_redrot.json"
    model_artifact.write_text("test-only mocked artifact", encoding="utf-8")
    monkeypatch.setattr(routes.settings, "enable_experimental_risk_model", True)
    monkeypatch.setattr(routes.settings, "risk_model_path", str(tmp_path / "xgboost_risk_prototype.json"))
    monkeypatch.setattr(
        routes,
        "fetch_current_weather",
        lambda farm, db: SimpleNamespace(
            observed_at=datetime.now(timezone.utc),
            temperature_mean=29.5,
            relative_humidity=84.5,
            precipitation=5.0,
            wind_speed=6.0,
            dew_point=25.8,
        ),
    )

    monkeypatch.setattr(
        routes,
        "predict_disease_presence",
        lambda disease, features, path: {
            "status": "experimental_observation_time_association",
            "disease_class": disease,
            "disease_presence_score": 0.825,
            "score_note": "Uncalibrated model score.",
            "processing_time_ms": 12,
            "model_version": "xgboost_redrot",
            "primary_drivers": [
                {"feature": "relative_humidity_pct", "value": 84.5, "shap_value": 1.45, "effect": "increases_score"},
                {"feature": "dew_point_c", "value": 25.8, "shap_value": 0.92, "effect": "increases_score"},
            ],
            "input_features": features,
            "scientific_disclosure": "Not a future disease forecast or confirmed diagnosis.",
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
        "disease_class": "RedRot"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "experimental_observation_time_association"
    assert data["disease_presence_score"] == 0.825
    assert data["disease_class"] == "RedRot"
    assert len(data["primary_drivers"]) == 2
    assert data["saved_to_history"] is True

    pred_id = data["id"]
    expl_res = client.get(f"/api/v1/risk/{pred_id}/explanation")
    assert expl_res.status_code == 200
    expl_data = expl_res.json()
    assert expl_data["status"] == "available"
    assert expl_data["explanation_type"] == "shap_tree"
    assert len(expl_data["drivers"]) == 2
