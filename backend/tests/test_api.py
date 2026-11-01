def register(client, email="farmer@example.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "a-strong-password-123", "full_name": "Test Farmer"},
    )


def test_registration_and_farm_crud(client):
    response = register(client)
    assert response.status_code == 201
    assert response.json()["email"] == "farmer@example.com"
    assert "sugarcane_session" in response.cookies

    farm = client.post(
        "/api/v1/farms",
        json={"name": "North Field", "latitude": 10.5, "longitude": 78.2, "soil_ph": 6.4, "crop_variety": "Co 86032"},
    )
    assert farm.status_code == 201
    assert farm.json()["latitude"] == 10.5
    assert farm.json()["soil_ph"] == 6.4
    assert client.get("/api/v1/farms").json()[0]["name"] == "North Field"
    preference = client.patch("/api/v1/auth/me", json={"preferred_language": "ta"})
    assert preference.status_code == 200
    assert preference.json()["preferred_language"] == "ta"
    maithili_preference = client.patch("/api/v1/auth/me", json={"preferred_language": "mai"})
    assert maithili_preference.status_code == 200
    assert maithili_preference.json()["preferred_language"] == "mai"

    updated = client.patch(f"/api/v1/farms/{farm.json()['id']}", json={"growth_stage": "Tillering"})
    assert updated.status_code == 200
    assert updated.json()["growth_stage"] == "Tillering"
    updated_ph = client.patch(f"/api/v1/farms/{farm.json()['id']}", json={"soil_ph": 6.8})
    assert updated_ph.status_code == 200
    assert updated_ph.json()["soil_ph"] == 6.8
    assert client.delete(f"/api/v1/farms/{farm.json()['id']}").status_code == 204


def test_account_deletion_removes_owned_data_and_session(client):
    register(client)
    farm = client.post("/api/v1/farms", json={"name": "Field to remove"})
    assert farm.status_code == 201
    deleted = client.delete("/api/v1/auth/me")
    assert deleted.status_code == 204
    assert "sugarcane_session" not in deleted.cookies
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/farms").status_code == 401


def test_users_cannot_access_another_users_farm(client):
    register(client, "first@example.com")
    farm = client.post("/api/v1/farms", json={"name": "Private Field"}).json()
    client.post("/api/v1/auth/logout")
    register(client, "second@example.com")
    assert client.get(f"/api/v1/farms/{farm['id']}").status_code == 404


def test_invalid_coordinate_pair_and_duplicate_account(client):
    assert register(client).status_code == 201
    invalid = client.post("/api/v1/farms", json={"name": "Invalid", "latitude": 10})
    assert invalid.status_code == 422
    invalid_ph = client.post("/api/v1/farms", json={"name": "Invalid pH", "soil_ph": 15})
    assert invalid_ph.status_code == 422
    duplicate = register(client)
    assert duplicate.status_code == 409


def test_disease_observations_require_review_before_training(client, monkeypatch):
    import app.api.routes as routes

    register(client)
    farm = client.post(
        "/api/v1/farms",
        json={"name": "Observation field", "latitude": 10.5, "longitude": 78.2, "soil_ph": 6.4},
    ).json()
    monkeypatch.setattr(routes, "fetch_current_weather", lambda farm, db: None)

    response = client.post(
        "/api/v1/disease-observations",
        json={
            "farm_id": farm["id"],
            "disease_class": "RedRot",
            "reported_outcome": "symptoms_seen",
            "research_consent": True,
            "notes": "Suspected leaf discoloration",
        },
    )
    assert response.status_code == 201
    assert response.json()["verification_status"] == "pending"
    assert response.json()["weather_captured"] is False
    assert "not a verified training label" in response.json()["message"]

    history = client.get("/api/v1/disease-observations")
    assert history.status_code == 200
    assert history.json()[0]["reported_outcome"] == "symptoms_seen"
    assert history.json()[0]["outcome"] is None
    assert client.get("/api/v1/admin/disease-observations/pending").status_code == 403


def test_prediction_is_explicitly_unavailable_without_model(client, monkeypatch):
    import app.api.routes as routes
    monkeypatch.setattr(routes.settings, "enable_experimental_risk_model", False)
    register(client)
    farm = client.post("/api/v1/farms", json={"name": "No model"}).json()
    result = client.post(
        "/api/v1/risk/predict",
        json={
            "farm_id": farm["id"],
            "disease_class": "RedRot",
            "period_start": "2026-01-01T00:00:00Z",
            "period_end": "2026-01-08T00:00:00Z",
        },
    )
    assert result.status_code == 503
    assert result.json()["detail"]["code"] == "risk_model_unavailable"
    assert "No score" in result.json()["detail"]["message"]


def test_upload_content_is_validated_not_just_extension(client):
    register(client)
    response = client.post(
        "/api/v1/diagnosis/predict",
        files={"file": ("leaf.jpg", b"this is not an image", "image/jpeg")},
    )
    assert response.status_code == 415


def test_experimental_image_result_is_labeled_uncalibrated_and_not_saved(client, monkeypatch, tmp_path):
    from io import BytesIO

    import app.api.routes as routes
    from PIL import Image

    register(client)
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"test artifact marker")
    monkeypatch.setattr(routes.settings, "image_model_path", str(artifact))
    monkeypatch.setattr(routes.settings, "enable_experimental_image_model", True)
    monkeypatch.setattr(
        routes,
        "classify_image",
        lambda raw: {
            "status": "experimental",
            "predicted_class": "Healthy",
            "uncalibrated_score": 0.72,
            "alternative_predictions": [],
            "model_version": "test-version",
            "processing_time_ms": 1,
            "explanation": None,
            "warning": "Not a confirmed diagnosis.",
            "saved_to_history": False,
        },
    )
    buffer = BytesIO()
    Image.new("RGB", (16, 16), "green").save(buffer, format="JPEG")

    response = client.post(
        "/api/v1/diagnosis/predict",
        files={"file": ("leaf.jpg", buffer.getvalue(), "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "experimental"
    assert response.json()["uncalibrated_score"] == 0.72
    assert response.json()["saved_to_history"] is True
    history = client.get("/api/v1/diagnosis/history")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["status"] == "experimental"


def test_experimental_model_file_is_not_used_without_opt_in(client, monkeypatch, tmp_path):
    import app.api.routes as routes

    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"test artifact marker")
    monkeypatch.setattr(routes.settings, "image_model_path", str(artifact))
    monkeypatch.setattr(routes.settings, "enable_experimental_image_model", False)
    register(client)

    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (16, 16), "green").save(buffer, format="JPEG")
    response = client.post(
        "/api/v1/diagnosis/predict",
        files={"file": ("leaf.jpg", buffer.getvalue(), "image/jpeg")},
    )
    assert response.status_code == 503


def test_readiness_marks_opted_in_image_model_as_experimental(client, monkeypatch, tmp_path):
    import app.api.routes as routes

    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"test artifact marker")
    monkeypatch.setattr(routes.settings, "image_model_path", str(artifact))
    monkeypatch.setattr(routes.settings, "enable_experimental_image_model", True)

    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["image_model"] == "experimental_enabled"


def test_weather_refresh_caches_provider_data_and_marks_fallback_stale(client, monkeypatch):
    import app.api.routes as routes

    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "current": {
                    "time": "2026-10-28T03:30",
                    "temperature_2m": 27.1,
                    "relative_humidity_2m": 61,
                    "dew_point_2m": 18.5,
                    "precipitation": 0.0,
                    "wind_speed_10m": 9.2,
                },
                "current_units": {"temperature_2m": "°C"},
            }

    class MockClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, *args, **kwargs):
            return MockResponse()

    register(client)
    farm = client.post(
        "/api/v1/farms",
        json={"name": "Weather field", "latitude": 10.5, "longitude": 78.2},
    ).json()
    monkeypatch.setattr(routes.httpx, "Client", MockClient)
    fresh = client.get(f"/api/v1/weather/current?farm_id={farm['id']}")
    assert fresh.status_code == 200
    assert fresh.json()["status"] == "available"
    assert fresh.json()["cached"] is False
    assert fresh.json()["observation"]["temperature_mean"] == 27.1

    class FailedClient(MockClient):
        def get(self, *args, **kwargs):
            import httpx

            raise httpx.TimeoutException("provider timeout")

    monkeypatch.setattr(routes.httpx, "Client", FailedClient)
    stale = client.get(f"/api/v1/weather/current?farm_id={farm['id']}")
    assert stale.status_code == 200
    assert stale.json()["status"] == "stale"
    assert stale.json()["cached"] is True
    assert stale.json()["timestamp"] is not None


def test_gemini_weather_guidance_uses_farm_weather_and_saved_language(client, monkeypatch):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    import app.api.routes as routes

    observed_at = datetime(2026, 10, 31, 4, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(routes.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(
        routes,
        "fetch_current_weather",
        lambda farm, db: SimpleNamespace(
            observed_at=observed_at,
            temperature_mean=29.5,
            relative_humidity=84.5,
            dew_point=25.8,
            precipitation=5.0,
            wind_speed=6.0,
        ),
    )
    recent_weather = {
        "provider": "Open-Meteo",
        "available_days": 7,
        "days": [{"date": "2026-10-30", "mean_relative_humidity_pct": 84.0}],
    }
    monkeypatch.setattr(routes, "fetch_recent_weather_context", lambda farm, end_at: recent_weather)
    captured = {}

    def fake_guidance(**kwargs):
        captured.update(kwargs)
        return {
            "risk_level": "moderate",
            "risk_reason": "Recent humid weather may favor monitoring.",
            "summary": "Check the crop after the humid weather.",
            "weather_effect": "Humidity is 84.5% and rain is 5 mm.",
            "actions": ["Walk the field and inspect the crop."],
            "watch_for": ["Look for unusual leaf changes."],
            "limitations": "Weather alone does not confirm disease.",
        }

    monkeypatch.setattr(routes, "generate_weather_guidance", fake_guidance)
    register(client)
    client.patch("/api/v1/auth/me", json={"preferred_language": "te"})
    farm = client.post(
        "/api/v1/farms",
        json={
            "name": "Private weather field",
            "latitude": 10.5,
            "longitude": 78.2,
            "soil_ph": 6.4,
            "crop_variety": "Co 86032",
            "growth_stage": "Tillering",
        },
    ).json()

    response = client.post(
        "/api/v1/weather/guidance",
        json={"farm_id": farm["id"], "disease_class": "RedRot", "language_code": "te"},
    )

    assert response.status_code == 200
    assert response.json()["risk_level"] == "moderate"
    assert response.json()["weather_history_days"] == 7
    assert response.json()["weather_freshness"] == "current"
    assert response.json()["weather_observed_at"] == observed_at.isoformat().replace("+00:00", "Z")
    assert response.json()["actions"] == ["Walk the field and inspect the crop."]
    assert captured["language_code"] == "te"
    assert captured["weather"]["relative_humidity_pct"] == 84.5
    assert captured["weather"]["rainfall_mm"] == 5.0
    assert captured["crop_variety"] == "Co 86032"
    assert captured["growth_stage"] == "Tillering"
    assert captured["soil_ph"] == 6.4
    assert captured["location"] == {"latitude": 10.5, "longitude": 78.2}
    assert captured["recent_weather"] == recent_weather


def test_gemini_weather_guidance_requires_backend_key(client, monkeypatch):
    import app.api.routes as routes

    monkeypatch.setattr(routes.settings, "gemini_api_key", "")
    register(client)
    response = client.post(
        "/api/v1/weather/guidance",
        json={"farm_id": "unneeded-before-key-check", "disease_class": "RedRot"},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "gemini_not_configured"


def test_recent_weather_context_aggregates_only_observed_seven_day_window(monkeypatch):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    import app.api.routes as routes

    captured = {}

    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "hourly": {
                    "time": ["2026-10-30T03:00", "2026-10-30T04:00", "2026-10-31T05:00"],
                    "temperature_2m": [24.0, 26.0, 40.0],
                    "relative_humidity_2m": [80.0, 90.0, 99.0],
                    "precipitation": [1.0, 3.0, 10.0],
                }
            }

    class MockClient:
        def __init__(self, **kwargs):
            captured["timeout"] = kwargs["timeout"]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url, *, params):
            captured.update({"url": url, "params": params})
            return MockResponse()

    monkeypatch.setattr(routes.httpx, "Client", MockClient)
    farm = SimpleNamespace(latitude=10.5, longitude=78.2)
    end_at = datetime(2026, 10, 31, 4, 0, tzinfo=timezone.utc)

    result = routes.fetch_recent_weather_context(farm, end_at)

    assert captured["params"]["latitude"] == 10.5
    assert captured["params"]["longitude"] == 78.2
    assert captured["params"]["past_days"] == 7
    assert result["available_days"] == 1
    assert result["days"] == [{
        "date": "2026-10-30",
        "hours_with_temperature": 2,
        "mean_temperature_c": 25.0,
        "mean_relative_humidity_pct": 85.0,
        "hours_relative_humidity_at_least_80_pct": 2,
        "total_precipitation_mm": 4.0,
    }]


def test_admin_routes_require_admin_role(client):
    register(client)
    assert client.get("/api/v1/admin/models").status_code == 403


def test_health_endpoints_report_api_and_dependency_status(client):
    assert client.get("/api/v1/health/live").json() == {"status": "ok"}
    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["checks"]["database"] == "ok"
    assert ready.json()["checks"]["image_model"] in ("disabled", "experimental_enabled")
    assert ready.json()["checks"]["risk_model"] in ("disabled", "experimental_enabled", "unavailable")
