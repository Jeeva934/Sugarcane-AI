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
        json={"name": "North Field", "latitude": 10.5, "longitude": 78.2, "crop_variety": "Co 86032"},
    )
    assert farm.status_code == 201
    assert farm.json()["latitude"] == 10.5
    assert client.get("/api/v1/farms").json()[0]["name"] == "North Field"
    preference = client.patch("/api/v1/auth/me", json={"preferred_language": "ta"})
    assert preference.status_code == 200
    assert preference.json()["preferred_language"] == "ta"

    updated = client.patch(f"/api/v1/farms/{farm.json()['id']}", json={"growth_stage": "Tillering"})
    assert updated.status_code == 200
    assert updated.json()["growth_stage"] == "Tillering"
    assert client.delete(f"/api/v1/farms/{farm.json()['id']}").status_code == 204


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
    duplicate = register(client)
    assert duplicate.status_code == 409


def test_prediction_is_explicitly_unavailable_without_model(client):
    register(client)
    farm = client.post("/api/v1/farms", json={"name": "No model"}).json()
    result = client.post(
        "/api/v1/risk/predict",
        json={
            "farm_id": farm["id"],
            "disease_class": "unconfigured",
            "period_start": "2026-01-01T00:00:00Z",
            "period_end": "2026-01-08T00:00:00Z",
        },
    )
    assert result.status_code == 503
    assert result.json()["detail"]["code"] == "risk_model_unavailable"
    assert "No risk score" in result.json()["detail"]["message"]


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
    assert response.json()["saved_to_history"] is False


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


def test_admin_routes_require_admin_role(client):
    register(client)
    assert client.get("/api/v1/admin/models").status_code == 403


def test_health_endpoints_report_api_and_dependency_status(client):
    assert client.get("/api/v1/health/live").json() == {"status": "ok"}
    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["checks"]["database"] == "ok"
    assert ready.json()["checks"]["image_model"] == "unavailable"
    assert ready.json()["checks"]["risk_model"] == "unavailable"
